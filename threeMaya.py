__version__ = '0.3'
__author__ = 'Thomas Guittonneau'
__email__ = 'wougzy@gmail.com'


# Three.js scene exporter for Maya
# JSON Model format 3.1

# todo:
# -secure skeleton/weights export (maxInf, 2 joints)
# -secure file writing
# -export vertex colors
# -export blendshapes
# -better texture handling (bake, 2d placement)
# -export bump textures


import os.path
import shutil
import pymel.core as pymel


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

        nodes = pymel.ls(args, et='transform')
        if not nodes:
            nodes = pymel.selected(et='transform')

        _sl = pymel.selected()
        pymel.select(nodes, hi=1)
        nodes = pymel.selected()
        pymel.select(_sl)

        geo = []
        for node in pymel.ls(nodes, et='mesh'):
            msh = node.getParent()
            if not msh in geo:
                geo.append(msh)

        self.meshes = []
        self.shapes = []

        for node in geo:
            for shp in node.getShapes():
                if isinstance(shp, pymel.nt.Mesh) and shp.io.get()==0:
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
        #self.db['colors'] = []

        self.db['metadata']['vertices'] = 0
        self.db['metadata']['faces'] = 0

        for msh,shp in zip(self.meshes, self.shapes):
            self.exportGeometry(msh,shp)

        self.db['metadata']['materials'] = len( self.db['materials'] )
        self.db['metadata']['uvs'] = len(self.db['uvs'][0])/2
        self.db['metadata']['normals'] = len(self.db['normals'])/3





    def exportGeometry(self, msh, shp):

        # export materials
        sgs = list(set( shp.outputs(type='shadingEngine') ))
        sgf = []

        if len(sgs) > 1:
            for sg in sgs:
                ids = []
                for _f in pymel.ls( sg.members(), flatten=1 ):
                    if isinstance(_f, pymel.MeshFace):
                        ids.append(_f)
                sgf.append(ids)


        sgi = []

        for sg in sgs:
            mat = sg.surfaceShader.inputs()[0]
            if str(mat) in self.materials:
                pass
            else:
                i = len(self.materials)
                self.materials.append(str(mat))

                m = {
                    'id' : i,
                    'name' : str(mat),

                    'DbgColor' : 0xFFFFFF,
                    'DbgIndex' : i,
                    'DbgName'  : str(mat),

                    #'blending' : 'NormalBlending',
                    #'depthTest' : True,
                    #'depthWrite' : True,
                    #'visible' : True
                    #'wireframe': True,
                    #'vertexColors' : False,
                }

                self.db['materials'].append(m)


                _nt = pymel.nodeType(mat)
                if _nt in ('lambert', 'phong', 'blinn'):
                    m['shading'] = 'Phong'
                    m['colorDiffuse'] = mat.color.get()
                    #m['colorAmbient'] = mat.ambientColor.get()
                    m['colorEmissive'] = mat.incandescence.get()

                    self.setTextureInfo(i, 'mapDiffuse', mat.color )
                    #self.setTextureInfo(i, 'mapLight', mat.ambientColor )
                    self.setTextureInfo(i, 'mapBump', mat.normalCamera )

                    _t = mat.transparency.get()
                    _t = 1 - (_t[0]+_t[1]+_t[2]) / 3
                    if _t < 1:
                        m['transparency'] = _t
                        m['transparent'] = True

                if _nt in ('phong', 'blinn'):
                    m['colorSpecular'] = mat.specularColor.get()
                    m['specularCoef'] = 10

                    self.setTextureInfo(i, 'mapSpecular', mat.specularColor )

                if _nt == 'surfaceShader':
                    m['shading'] = 'Basic'
                    m['colorDiffuse'] = mat.outColor.get()


                if shp.doubleSided.get():
                    m['doubleSided'] = True
                elif shp.opposite.get():
                    m['flipSided'] = True

            sgi.append( self.materials.index(str(mat)) )



        # export vertices
        _v = len(msh.vtx)
        _voffset = self.db['metadata']['vertices']
        self.db['metadata']['vertices'] += _v
        self.vertices.append(_v)

        for v in msh.vtx:
            self.db['vertices'] += roundList( v.getPosition(space='world'), DECIMALS_VERTICES )



        # export faces
        _f = len(msh.faces)
        _foffset = self.db['metadata']['faces']
        self.db['metadata']['faces'] += _f
        self.faces.append(_f)


        _noffset = len(self.db['normals'])/3
        _uvoffset = len(self.db['uvs'][0])/2

        uvs = {}
        normals = {}
        colors = {}

        dbuv = []
        dbn  = []


        for f in msh.faces:
            vtx = [x+_voffset for x in f.getVertices()]
            if len(vtx)>4:
                self.db['metadata']['faces'] -= 1
                self.faces[-1] -= 1

            else:
                dbf = [0]
                dbf += vtx
                if len(vtx)==4:
                    dbf[0] += FACE_QUAD


                dbf[0] += FACE_MATERIAL

                if len(sgs)==1:
                    dbf.append(sgi[0])
                else:
                    for i,fset in enumerate(sgf):
                        if f in fset:
                            dbf.append(sgi[i])
                            break


                dbf[0] += FACE_VERTEX_UV

                for v,uv in zip( vtx, zip(*f.getUVs()) ):
                    uv = roundList(uv, DECIMALS_UVS)

                    if not uvs.get(v):
                        uvs[v] = []

                    done = False
                    for _i,_uv in uvs[v]:
                        if _uv == uv:
                            dbf.append(_i)
                            done = True
                            break

                    if not done:
                        i = len(dbuv)/2
                        dbuv += uv
                        uvs[v].append((i,uv))
                        dbf.append(i)


                dbf[0] += FACE_VERTEX_NORMAL

                for v,n in zip( vtx, f.getNormals() ):
                    n = roundList(n, DECIMALS_NORMALS)

                    if not normals.get(v):
                        normals[v] = []

                    done = False
                    for _i,_n in normals[v]:
                        if _n == n:
                            dbf.append(_i+_noffset)
                            done = True
                            break

                    if not done:
                        i = len(dbn)/3
                        dbn += n
                        normals[v].append((i,n))
                        dbf.append(i+_noffset)

                self.db['faces'] += dbf


        self.db['uvs'][0].extend(dbuv)
        self.db['normals'].extend(dbn)





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

                    nweights=[]
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

                _m = pymel.dt.TransformationMatrix( inf.worldMatrix.get() )
                if _parent:
                    _m *= _parent.worldInverseMatrix.get()

                b['pos'] = roundList( _m.getTranslation('transform'), DECIMALS_POS )
                b['rotq'] = roundList( _m.getRotationQuaternion(), DECIMALS_ROT )

                self.bones.append(b)


            self.db['metadata']['bones'] = len(self.bones)
            self.db['bones'] = self.bones





    def exportAnimation(self, _start, _end):

            self.infs = [pymel.PyNode(str(x)) for x in self.infs]

            # export simple anim
            _keys = pymel.keyframe(self.infs, query=True, timeChange=True)

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
                    )[ pymel.currentUnit(query=True, time=True) ]

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

                        _m = pymel.dt.TransformationMatrix( inf.worldMatrix.get(time=_t) )
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
            _nt = pymel.nodeType(src)

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



    def write(self, name, path, compact=False):
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
        f.write( self.encode(compact) )
        f.close()





def roundList(array, decimals=4):
    new = []
    for i,v in enumerate(array):
        new.append(round(v,decimals))
    return new

