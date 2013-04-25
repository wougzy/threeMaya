__version__ = '0.1'
__author__ = 'Thomas Guittonneau'
__email__ = 'mantus@free.fr'


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


        #db init
        self.db = {
            'metadata': {
                'formatVersion' : 3.1,
                'generatedBy'   : "yz Maya2012 Exporter"
                },
            'scale': 1,

            'vertices': [],
            'normals': [],
            'colors': [],
            'uvs': [],
            'faces': [],

            'bones': [],

            'materials': [],
        }


        #export vertices
        self.db['metadata']['vertices'] = len(self.msh.vtx)

        for v in self.msh.vtx:
            self.db['vertices'] += roundList( v.getPosition(space='world'), DECIMALS_VERTICES )


        #export faces
        self.db['metadata']['faces'] = len(self.msh.faces)

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
                fa.append(0)


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



        #default mat
        m = {
            'DbgColor' : 0xFFFFFF,
            'DbgIndex' : 0,
            'DbgName'  : 'dummy',
            'blending' : 'NormalBlending',

            'colorDiffuse'  : (1,1,1),
            'colorAmbient'  : (0,0,0),
            'colorSpecular' : (.1,.1,.1),
            'mapDiffuse' : 'checker.jpg',

            'depthTest' : True,
            'depthWrite' : True,
            'shading' : 'Phong',
            'specularCoef' : 10,
            'transparency' : 1.0,
            'transparent' : False,
            'vertexColors' : False
        }
        self.db['materials'].append(m)

        self.db['metadata']['materials'] = len( self.db['materials'] )


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


            self.db['bones'] = bones
            self.db['metadata']['bones'] = len(bones)



            #export simple anim
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

            _keys = pymel.keyframe(infs, query=True, timeChange=True)
            _start = min(_keys)
            _end = max(_keys)

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




    def encode(self, compact=False ):
        if not compact:
            return json.dumps(self.db, cls=DecimalEncoder, separators=(',', ': '), indent=2 )
        else:
            return json.dumps(self.db, cls=DecimalEncoder, separators=(',', ':') )



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




