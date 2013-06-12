__version__ = '0.2'
__author__ = 'Thomas Guittonneau'
__email__ = 'wougzy@gmail.com'


# Three.js scene exporter for Maya
# JSON Model format 3.1

# todo:
# -secure skeleton/weights export (maxInf, 2 joints)
# -secure file writing
# -export vertex colors
# -export blendshapes


import os.path
import shutil
import pymel.core as pymel
import json


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
DECIMALS_ROT      = 3
DECIMALS_TIME     = 3


class Exporter(object):

    def __init__(self, *args):

        nodes = pymel.ls(args, et='transform')
        if not nodes:
            nodes = pymel.selected(et='transform')

        self.msh = None

        for node in nodes:
            for shp in node.getShapes():
                if isinstance(shp, pymel.nt.Mesh):
                    self.msh = node
                    break

        if not self.msh:
            raise RuntimeError('no mesh provided')
        else:
            print '# Exporting MESH: %s'%self.msh

        self.shape = None
        for _shp in self.msh.getShapes():
            if _shp.io.get()==0:
                self.shape = _shp
                break



        #db init
        self.db = {
            'metadata': {
                'formatVersion' : 3.1,
                'generatedBy'   : "yz Maya2012 Exporter"
                },
            'scale': 1,
        }


        #export materials
        self.db['materials'] = []
        self.textures = []

        sgs = list(set( self.shape.outputs(type='shadingEngine') ))
        sgf = []

        if len(sgs) > 1:
            for sg in sgs:
                ids = []
                for _f in pymel.ls( sg.members(), flatten=1 ):
                    if isinstance(_f, pymel.MeshFace):
                        ids.append(_f)
                sgf.append(ids)


        for i,sg in enumerate(sgs):

            mat = sg.surfaceShader.inputs()[0]

            m = {
                'id' : i,
                'name' : str(mat),

                'DbgColor' : 0xFFFFFF,
                'DbgIndex' : i,
                'DbgName'  : str(mat),

                'shading' : 'Lambert',

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
                m['colorAmbient'] = mat.ambientColor.get()

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


            if self.shape.doubleSided.get():
                m['doubleSided'] = True
            elif self.shape.opposite.get():
                m['flipSided'] = True


        self.db['metadata']['materials'] = len( self.db['materials'] )



        #export vertices
        self.db['metadata']['vertices'] = len(self.msh.vtx)
        self.db['vertices'] = []

        for v in self.msh.vtx:
            self.db['vertices'] += roundList( v.getPosition(space='world'), DECIMALS_VERTICES )


        #export faces
        self.db['metadata']['faces'] = len(self.msh.faces)
        self.db['faces'] = []
        self.db['uvs'] = []
        self.db['normals'] = []
        #self.db['colors'] = []

        uvs = {}
        normals = {}
        colors = {}

        dbuv = []
        dbn  = []

        for f in self.msh.faces:
            vtx = f.getVertices()
            if len(vtx)>4:
                self.db['metadata']['faces'] -= 1

            else:
                fa = [0]
                fa += vtx
                if len(vtx)==4:
                    fa[0] += FACE_QUAD

                fa[0] += FACE_MATERIAL
                if len(sgs)==1:
                    fa.append(0)
                else:
                    for i,fset in enumerate(sgf):
                        if f in fset:
                            fa.append(i)
                            break


                fa[0] += FACE_VERTEX_UV

                for v,uv in zip( vtx, zip(*f.getUVs()) ):
                    uv = roundList(uv, DECIMALS_UVS)

                    if not uvs.get(v):
                        uvs[v] = []

                    done = False
                    for _i,_uv in uvs[v]:
                        if _uv == uv:
                            fa.append(_i)
                            done = True
                            break

                    if not done:
                        i = len(dbuv)/2
                        dbuv += uv
                        uvs[v].append((i,uv))
                        fa.append(i)


                fa[0] += FACE_VERTEX_NORMAL

                for v,n in zip( vtx, f.getNormals() ):
                    n = roundList(n, DECIMALS_NORMALS)

                    if not normals.get(v):
                        normals[v] = []

                    done = False
                    for _i,_n in normals[v]:
                        if _n == n:
                            fa.append(_i)
                            done = True
                            break

                    if not done:
                        i = len(dbn)/3
                        dbn += n
                        normals[v].append((i,n))
                        fa.append(i)

                self.db['faces'] += fa

        self.db['uvs'].append(dbuv)
        self.db['metadata']['uvs'] = len(dbuv)/2

        self.db['normals'] = dbn
        self.db['metadata']['normals'] = len(dbn)/3



        #export skeleton
        skin = self.msh.listHistory( type='skinCluster' )
        if skin:
            skin = skin[0]
        else:
            skin = None

        if skin:
            # export weights
            # convert skinCluster with 2 bones per vertex

            self.db['skinIndices'] = []
            self.db['skinWeights'] = []

            infs = skin.getInfluence()
            infid = range(len(infs))

            weights = []
            for wmap in skin.getWeights(self.msh):
                weights.append(wmap)

            nweights=[]
            for w in weights:
                w = zip(infid,w)
                w = sorted(w, key=lambda vweight: vweight[1])[-2:]
                n = w[0][1]+w[1][1]

                self.db['skinIndices'].append(w[1][0])
                self.db['skinIndices'].append(w[0][0])
                w1 = round( w[1][1]/n, DECIMALS_WEIGHTS )
                w0 = round( w[0][1]/n, DECIMALS_WEIGHTS )
                self.db['skinWeights'].append(w1)
                self.db['skinWeights'].append(w0)


            bones  = []

            for inf in infs:
                b = {}
                b['name'] = str(inf).split('|')[-1].split(':')[-1]

                b['parent'] = -1
                _parent = None
                for p in inf.getAllParents():
                    if p in infs:
                        _parent = p
                        b['parent'] = infs.index(p)
                        break

                _m = pymel.dt.TransformationMatrix( inf.worldMatrix.get() )
                if _parent:
                    _m *= _parent.worldInverseMatrix.get()

                b['pos'] = roundList( _m.getTranslation('transform'), DECIMALS_POS )
                b['rotq'] = roundList( _m.getRotationQuaternion(), DECIMALS_ROT )

                bones.append(b)


            self.db['metadata']['bones'] = len(bones)
            self.db['bones'] = bones




            #export simple anim
            _keys = pymel.keyframe(infs, query=True, timeChange=True)

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


                anim['length'] = round( (_end-_start)/float(anim['fps']), DECIMALS_TIME )
                anim['hierarchy'] = []

                for i,inf in enumerate(infs):
                    _inf = {}

                    _parent = bones[i]['parent']
                    _inf['parent'] = _parent

                    if _parent != -1:
                        _parent = infs[_parent]
                    else:
                        _parent = None

                    _inf['keys'] = []
                    _start = min(_keys)
                    _end = max(_keys)

                    for frame in xrange( _end - _start ):
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




    def encode(self, compact=False ):
        #todo: smart compact mode
        if not compact:
            return json.dumps(self.db, cls=DecimalEncoder, separators=(',', ': '), indent=2 )
        else:
            return json.dumps(self.db, cls=DecimalEncoder, separators=(',', ':') )



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


class DecimalEncoder(json.JSONEncoder):
    def _iterencode(self, o, markers=None):
        if isinstance(o, float):
            return (str(o) for o in [o])
        return super(DecimalEncoder, self)._iterencode(o, markers)




