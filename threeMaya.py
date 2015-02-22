__version__ = '0.4'
__author__ = 'Thomas Guittonneau'
__email__ = 'wougzy@gmail.com'


# Three.js scene exporter for Maya
# JSON Model format 3.1

# todo:
# -basic UI
# -secure skeleton/weights export (maxInf, 2 joints)
# -secure file writing
# -export blendshapes
# -better texture handling (bake, 2d placement)
# -export bump textures


import sys
import os.path
import shutil
import json
import maya.OpenMaya as om
import pymel.core as pm


FACE_QUAD          = 0b00000001
FACE_MATERIAL      = 0b00000010
FACE_UV            = 0b00000100
FACE_VERTEX_UV     = 0b00001000
FACE_NORMAL        = 0b00010000
FACE_VERTEX_NORMAL = 0b00100000
FACE_COLOR         = 0b01000000
FACE_VERTEX_COLOR  = 0b10000000

DECIMALS_VERTICES = 4
DECIMALS_UVS      = 3
DECIMALS_NORMALS  = 3
DECIMALS_COLOR    = 3
DECIMALS_WEIGHTS  = 2
DECIMALS_POS      = 3
DECIMALS_ROT      = 5
DECIMALS_TIME     = 3

ORDERED_DICTS = (
    ( 'metadata', 'scale', 'materials', 'vertices', 'normals', 'colors', 'uvs', 'faces',
        'morphTargets', 'bones', 'skinIndices', 'skinWeights', 'animation' ),

    ( 'formatVersion', 'generatedBy', 'vertices', 'faces', 'normals', 'colors', 'uvs', 'materials', 'morphTargets', 'bones' ),

    ( 'name', 'id', 'DbgName', 'DbgColor', 'DbgIndex', 'shading', 'blending',
        'colorAmbient', 'colorDiffuse', 'colorSpecular', 'mapDiffuse',
        'specularCoef', 'transparency', 'transparent',
        'depthTest', 'depthWrite', 'doubleSided', 'vertexColors' )
)


class Exporter(object):

    def __init__(self, *args):

        nodes = pm.ls(args, et='transform')
        if not nodes:
            nodes = pm.selected(et='transform')

        _sl = pm.selected()
        pm.select(nodes, hi=1)
        nodes = pm.selected()
        pm.select(_sl)

        geo = []
        for node in pm.ls(nodes, et='mesh'):
            msh = node.getParent()
            if not msh in geo:
                geo.append(msh)

        self.meshes = []
        self.shapes = []

        for node in geo:
            for shp in node.getShapes():
                if isinstance(shp, pm.nt.Mesh) and shp.io.get()==0 and shp.isVisible():
                    self.meshes.append(node)
                    self.shapes.append(shp)

        if not self.meshes:
            raise RuntimeError('no mesh provided')
        else:
            print '# Exporting MESHES: %s'%str(self.meshes)



        # db init
        self.db = {
            'metadata': {
                'formatVersion' : 3.1,
                'generatedBy'   : "yz Maya2012 Exporter"
                },
            'scale': 1,
        }


        self.materials = []
        self.textures = []
        self.db['materials'] = []

        self.vertices = []
        self.faces = []
        self.db['vertices'] = []
        self.db['faces'] = []
        self.db['uvs'] = [[]]
        self.db['normals'] = []
        self.db['colors'] = [16777215] #white for colorless

        self.db['metadata']['vertices'] = 0
        self.db['metadata']['faces'] = 0

        self._prg_msh = len(self.shapes)
        self._prg_count = 0
        pm.progressWindow( endProgress=True )
        pm.progressWindow( title="Exporting meshes", progress=0, status="", maxValue=self._prg_msh )

        try:
            for msh,shp in zip(self.meshes, self.shapes):
                self.exportGeometry(msh,shp)
        except:
            pm.progressWindow( endProgress=True )
            from traceback import print_tb
            print sys.exc_info()[0]
            print_tb(sys.exc_info()[2])
            return None

        pm.progressWindow( endProgress=True )


        self.db['metadata']['materials'] = len( self.db['materials'] )
        self.db['metadata']['uvs'] = len(self.db['uvs'][0])/2
        self.db['metadata']['normals'] = len(self.db['normals'])/3





    def exportGeometry(self, msh, shp):

        # api calls
        dag = shp.__apiobject__()
        mshfn = om.MFnMesh(dag)

        # export materials
        pm.progressWindow( edit=True, status='mesh %s/%s (%s): writing materials...'%(self._prg_count,self._prg_msh,msh) )

        sgs = []
        sgf = []

        def faces(x):
          f = []
          for fs in x:
            if fs.startswith('f'):
              fs = fs.split('[')[1].split(']')[0]
              if ':' in fs:
                a, b = fs.split(':')
                a, b = int(a), int(b)
                f.extend(range(a, b + 1))
              else:
                f.append(int(fs))
          return f

        _o = shp.instObjGroups[0].objectGroups.outputs(type='shadingEngine')
        if _o:
            # multi mat
            for _id in shp.instObjGroups[0].objectGroups.getArrayIndices():
                og = shp.instObjGroups[0].objectGroups[_id]
                f = faces( og.objectGrpCompList.get() )

                _sg = og.outputs()
                if _sg and f:
                    sgs.append(_sg[0])
                    sgf.append(f)

        else:
            # single mat
            _o = shp.instObjGroups[0].outputs(type='shadingEngine')
            sgs += _o

        doColors = shp.displayColors.get()


        sgi = []

        for sg in sgs:
            mat = sg.surfaceShader.inputs()[0]
            if str(mat) in self.materials:
                if doColors:
                    for m in self.db['materials']:
                        if m['name'] == str(mat):
                            m['vertexColors'] = True
                            break
            else:
                i = len(self.materials)
                self.materials.append(str(mat))

                m = {
                    'id' : i,
                    'name' : str(mat),

                    'DbgColor' : 0xFFFFFF,
                    'DbgIndex' : i,
                    'DbgName'  : str(mat),
                }

                self.db['materials'].append(m)


                _nt = pm.nodeType(mat)
                if _nt in ('lambert', 'phong', 'blinn', 'anisotropic'):
                    m['shading'] = 'Phong'
                    m['colorDiffuse'] = roundList( mat.color.get(), DECIMALS_COLOR )
                    _c = pm.dt.Vector(mat.ambientColor.get()) + mat.incandescence.get()
                    m['colorAmbient'] = roundList( _c, DECIMALS_COLOR )
                    #m['colorEmissive'] = mat.incandescence.get()
                    m['colorSpecular'] = [0,0,0]

                    self.setTextureInfo(i, 'mapDiffuse', mat.color )
                    self.setTextureInfo(i, 'mapLight', mat.ambientColor )
                    self.setTextureInfo(i, 'mapBump', mat.normalCamera )

                    _t = mat.transparency.get()
                    _t = 1 - (_t[0]+_t[1]+_t[2]) / 3
                    if _t < 1:
                        m['transparency'] = _t
                        m['transparent'] = True

                if _nt in ('phong', 'blinn', 'anisotropic'):
                    m['colorSpecular'] = roundList( mat.specularColor.get(), DECIMALS_COLOR )
                    m['specularCoef'] = 10
                    if _nt == 'blinn':
                        m['specularCoef'] = 4 / mat.eccentricity.get()
                    elif _nt == 'phong':
                        m['specularCoef'] = mat.cosinePower.get() * 2
                    if _nt == 'anisotropic':
                        m['specularCoef'] = 4 / mat.roughness.get()


                    self.setTextureInfo(i, 'mapSpecular', mat.specularColor )

                if _nt == 'surfaceShader':
                    m['shading'] = 'Basic'
                    m['colorDiffuse'] = roundList( mat.outColor.get(), DECIMALS_COLOR )


                if shp.doubleSided.get():
                    m['doubleSided'] = True
                elif shp.opposite.get():
                    m['flipSided'] = True

                if doColors:
                    m['vertexColors'] = True

            sgi.append( self.materials.index(str(mat)) )



        # export vertices
        _v = mshfn.numVertices()
        _voffset = self.db['metadata']['vertices']
        self.db['metadata']['vertices'] += _v
        self.vertices.append(_v)

        pm.progressWindow( edit=True, status='mesh %s/%s (%s): writing vertices...'%(self._prg_count,self._prg_msh,msh) )


        _pts = om.MPointArray()
        mshfn.getPoints(_pts, om.MSpace.kWorld)

        for i in xrange(_v):
            _p = [ _pts[i][0], _pts[i][1], _pts[i][2] ]
            self.db['vertices'] += roundList( _p, DECIMALS_VERTICES )


        # export faces
        _f = mshfn.numPolygons()
        self.db['metadata']['faces'] += _f
        self.faces.append(_f)

        pm.progressWindow( edit=True, status='mesh %s/%s (%s): writing faces...'%(self._prg_count,self._prg_msh,msh) )


        uvs = {}

        _noffset = len(self.db['normals'])/3
        _normals = om.MFloatVectorArray()
        mshfn.getNormals(_normals,om.MSpace.kWorld)
        for i in xrange(_normals.length()):
            _n = [ _normals[i][0], _normals[i][1], _normals[i][2] ]
            self.db['normals'] += roundList( _n, DECIMALS_NORMALS )
        _npf = om.MIntArray()
        _nid = om.MIntArray()
        mshfn.getNormalIds(_npf, _nid)

        _coffset = len(self.db['colors'])


        _vfoffset = 0

        it = om.MItMeshPolygon(dag)
        while not it.isDone():
            f = it.index()

            # vertices
            _vtx = om.MIntArray()
            it.getVertices( _vtx )
            vtx = [x+_voffset for x in _vtx]

            if len(vtx)>4:
                self.db['metadata']['faces'] -= 1
                self.faces[-1] -= 1
                it.next()
                _vfoffset += len(vtx)
                continue
            else:
                dbf = [0]
                dbf += vtx
                if len(vtx)==4:
                    dbf[0] += FACE_QUAD

            # material
            dbf[0] += FACE_MATERIAL

            if len(sgs)==1:
                dbf.append(sgi[0])
            else:
                for i,fset in enumerate(sgf):
                    if f in fset:
                        dbf.append(sgi[i])
                        break

            # uvs
            _u = om.MFloatArray()
            _v = om.MFloatArray()
            try:
                it.getUVs( _u, _v )
                dbf[0] += FACE_VERTEX_UV

                for v,uv in zip( vtx, zip(_u,_v) ):
                    uv = roundList(uv, DECIMALS_UVS)

                    if not uvs.get(v):
                        uvs[v] = []

                    exported = False
                    for _i,_uv in uvs[v]:
                        if _uv == uv:
                            dbf.append(_i)
                            exported = True
                            break

                    if not exported:
                        i = len(self.db['uvs'][0])/2
                        self.db['uvs'][0] += uv
                        uvs[v].append((i,uv))
                        dbf.append(i)
            except:
                pass
                #print '# warning: %s.f[%s] has no uv' % (shp, f)

            # normals
            dbf[0] += FACE_VERTEX_NORMAL

            for i in xrange( len(vtx) ):
                _n = _nid[i+_vfoffset]
                dbf.append(_n+_noffset)

            # colors
            if doColors:
                dbf[0] += FACE_VERTEX_COLOR

                for i in xrange( len(vtx) ):
                    if it.hasColor( i ):
                        color = om.MColor()
                        it.getColor( color, i )
                        c = (int(color[0]*255)<<16) + (int(color[1]*255)<<8) + int(color[2]*255)
                        self.db['colors'].append(c)
                        dbf.append(i+_vfoffset+_coffset)
                    else:
                        # white for colorless vertex
                        dbf.append(0)
                        _coffset -= 1


            _vfoffset += len(vtx)

            # add face
            self.db['faces'] += dbf
            it.next()


        self._prg_count += 1
        pm.progressWindow( edit=True, step=1 )




    def exportSkeleton(self):

        # export skeleton
        deformed = False

        for msh in self.shapes:
            skin = msh.listHistory( type='skinCluster' )
            if skin:
                deformed = True
                break

        if deformed:
            self.db['skinIndices'] = []
            self.db['skinWeights'] = []


            # export bones
            self.infs = []

            for msh in self.shapes:

                skin = msh.listHistory( type='skinCluster' )
                if skin:
                    skin = skin[0]
                else:
                    skin = None

                if skin:
                    infs = skin.getInfluence()
                    for inf in infs:
                        if not inf in self.infs:
                            self.infs.append(inf)


                    # export weights
                    # convert skinCluster with 2 bones per vertex
                    infid = [self.infs.index(x) for x in infs]

                    weights = []
                    for wmap in skin.getWeights(msh):
                        weights.append(wmap)

                    for w in weights:
                        if len(infid)>1:
                            w = zip(infid,w)
                            w = sorted(w, key=lambda vweight: vweight[1])[-2:]
                            n = w[0][1]+w[1][1]

                            self.db['skinIndices'].append(w[1][0])
                            self.db['skinIndices'].append(w[0][0])
                            w1 = round( w[1][1]/n, DECIMALS_WEIGHTS )
                            w0 = round( w[0][1]/n, DECIMALS_WEIGHTS )
                            self.db['skinWeights'].append(w1)
                            self.db['skinWeights'].append(w0)

                        else:
                            self.db['skinWeights'].append(1)
                            self.db['skinWeights'].append(0)
                            self.db['skinIndices'].append(infid[0])
                            self.db['skinIndices'].append(-1)


                else:
                    pass
                    #mais pas oublier de faire les mesh non anime aussi


            self.bones  = []

            for inf in self.infs:
                b = {}
                b['name'] = str(inf).split('|')[-1].split(':')[-1]

                b['parent'] = -1
                _parent = None
                for p in inf.getAllParents():
                    if p in self.infs:
                        _parent = p
                        b['parent'] = self.infs.index(p)
                        break

                _m = pm.dt.TransformationMatrix( inf.worldMatrix.get() )
                if _parent:
                    _m *= _parent.worldInverseMatrix.get()

                b['pos'] = roundList( _m.getTranslation('transform'), DECIMALS_POS )
                b['rotq'] = roundList( _m.getRotationQuaternion(), DECIMALS_ROT )

                self.bones.append(b)


            self.db['metadata']['bones'] = len(self.bones)
            self.db['bones'] = self.bones





    def exportAnimation(self, _start, _end):

            self.infs = [pm.PyNode(str(x)) for x in self.infs]

            # export simple anim
            _keys = pm.keyframe(self.infs, query=True, timeChange=True)

            if _keys:
                anim = {}
                self.db['animation'] = anim

                anim['name'] = 'anim0'

                fps = dict(
                    game = 15,
                    film = 24,
                    pal = 25,
                    ntsc = 30,
                    show = 48,
                    palf = 50,
                    ntscf = 60
                    )[ pm.currentUnit(query=True, time=True) ]

                anim['fps'] = fps

                anim['hierarchy'] = []

                for i,inf in enumerate(self.infs):
                    _inf = {}

                    _parent = self.bones[i]['parent']
                    _inf['parent'] = _parent

                    if _parent != -1:
                        _parent = self.infs[_parent]
                    else:
                        _parent = None

                    _inf['keys'] = []
                    #_start = min(_keys)
                    #_end = max(_keys)
                    anim['length'] = round( (_end-_start)/float(anim['fps']), DECIMALS_TIME )

                    for frame in xrange( int(_end - _start) ):
                        _t = frame+_start

                        _key = {}
                        _key['time'] = round( frame/float(fps), DECIMALS_TIME )

                        _m = pm.dt.TransformationMatrix( inf.worldMatrix.get(time=_t) )
                        if _parent:
                            _m *= _parent.worldInverseMatrix.get(time=_t)

                        _key['pos'] = roundList( _m.getTranslation('transform'), DECIMALS_POS )
                        _key['rot'] = roundList( _m.getRotationQuaternion(), DECIMALS_ROT )
                        if frame==0:
                            _key['scl'] = [1,1,1]

                        _inf['keys'].append(_key)

                    _inf['keys'].append( {'time': anim['length']} )

                    anim['hierarchy'].append(_inf)





    def setTextureInfo(self, i, mode, attr ):

        src = attr.inputs()
        ok = False

        if src:
            infos = {}
            infos['id'] = i
            infos['mode'] = mode

            src = src[0]
            _nt = pm.nodeType(src)

            if _nt == 'file':
                infos['file'] = os.path.realpath( src.fileTextureName.get() )
                ok = True

            elif _nt == 'bump2d':
                b = src.bumpInterp.get()
                if b == 0:
                    pass
                else:
                    mode = 'mapNormal'

            else:
                infos['bake'] = src
                ok = True


        if ok:

            if mode == 'mapDiffuse':
                del( self.db['materials'][i]['colorDiffuse'] )
            if mode == 'mapSpecular':
                del( self.db['materials'][i]['colorSpecular'] )

            self.db['materials'][i]['%sRepeat'%mode] = (True, True)

            self.textures.append(infos)

        #options: 'Repeat', 'Offset', 'Wrap', 'Anisotropy'
        #mode bump: 'mapBumpScale', 'mapNormalFactor'



    def encode(self, compact=False):

        self.dump = ''
        self.dump_indent = ''
        self.dump_step = 2

        self.iterencode(self.db)

        return self.dump



    def iterencode(self, o):

        if isinstance(o, dict):
            self.iterindent(1)
            self.dump += '{\n'

            keys = o.keys()
            order = {}
            for d in ORDERED_DICTS:
                if len(order) < len( set(keys).intersection(d) ):
                    order = {}
                    for i,de in enumerate(d):
                        order[de] = i
            keys = sorted( keys, key=lambda k: order.get(k) )

            last = len(keys)-1
            for i,key in enumerate(keys):
                self.dump += self.dump_indent
                self.dump += '"%s": ' % key

                self.iterencode(o[key])
                if i!=last:
                    self.dump += ','
                self.dump += '\n'

            self.iterindent(-1)
            self.dump += '%s}' % self.dump_indent

        elif isinstance(o, list) or isinstance(o, tuple):
            self.dump += '['

            last = len(o)-1
            for i,e in enumerate(o):
                if isinstance(e, dict):
                    self.dump += '\n%s' % self.dump_indent
                self.iterencode(e)
                if i != last:
                    self.dump += ','
                    if last < 5:
                        self.dump += ' '

            self.dump += ']'

        elif isinstance(o, bool):
            if o: self.dump += 'true'
            else: self.dump += 'false'

        elif isinstance(o, str) or isinstance(o, unicode):
            self.dump += '"%s"' % str(o)

        else:
            self.dump += str(o)



    def iterindent(self, i):

        v = len(self.dump_indent) + i*self.dump_step
        self.dump_indent = ''
        for i in xrange(v):
            self.dump_indent += ' '



    def write(self, name, path, dump=True, compact=False ):
        #todo: check path validity
        #todo: confirm overwrite


        #copy/generate texture file
        map_folder = os.path.join( path, name )

        for m in self.textures:
            mode = m['mode']
            i = m['id']

            f = m.get('file')
            if f:
                if not os.path.exists(map_folder):
                    os.makedirs(map_folder)
                shutil.copyfile(f, os.path.join(map_folder, os.path.basename(f)) )
            else:
                bake = m.get('bake')
                #todo: bake texture

            if f:
                self.db['materials'][i][mode] = '%s/%s' % (name, os.path.basename(f) )


        # write json file
        js = path+'/'+name+'.js'

        f = open(js,'w')
        if not dump:
            f.write( self.encode(compact) )
        else:
            f.write( json.dumps(self.db) )
        f.close()





def roundList(array, decimals=4):
    new = []
    for i,v in enumerate(array):
        new.append(round(v,decimals))
    return new

