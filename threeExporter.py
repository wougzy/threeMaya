from pymel.core import *
import json

FACE_QUAD          = 0b00000001
FACE_MATERIAL      = 0b00000010
FACE_UV            = 0b00000100
FACE_VERTEX_UV     = 0b00001000
FACE_NORMAL        = 0b00010000
FACE_VERTEX_NORMAL = 0b00100000
FACE_COLOR         = 0b01000000
FACE_VERTEX_COLOR  = 0b10000000


class Exporter(object):
    
    def __init__(self, *args):
        
        nodes = ls(args, et='transform')
        if not args:
            nodes = selected(et='transform')
        
        self.msh = None
        
        for node in nodes:
            for shp in node.getShapes():
                if isinstance(shp, nt.Mesh):
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
            
            'materials': [],
        }
        
        
        #export vertices
        self.db['metadata']['vertices'] = len(self.msh.vtx)
        
        for v in self.msh.vtx:
            self.db['vertices'] += list(v.getPosition())
            
        for i,f in enumerate(self.db['vertices']):
            self.db['vertices'][i]=round(f,5)


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
                    uv = (round(uv[0],4), round(uv[1],4) )
                    
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
                    n = (round(n[0],4), round(n[1],4), round(n[2],4) )
                    
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
        
        self.db['metadata']['materials'] = len(self.db['materials'])



        """
        #default skin
        self.db['bones'] = [
            {
                'parent':-1,
                'name': 'root',
                'pos': [0,0,0],
                'rotq': [0,0,0,1]
            }
        ]
        
        self.db['metadata']['bones'] = len(self.db['bones'])
        
        
        self.db['skinIndices'] = [0 for x in xrange(self.db['metadata']['vertices'])]
        self.db['skinWeights'] = [1 for x in xrange(self.db['metadata']['vertices'])]

        self.db['animation'] = {
            'name': 'anim0',
            'fps': 24,
            'length': 1,
            'hierarchy': [
                {
                    'parent': -1,
                    'keys': [
                        {
                            'time': 0,
                            'pos': [0,0,0],
                            'rot': [0,0,0,1],
                            'scl': [1,1,1]
                        }
                    ]
                }
            ]
        }
        """


    def encode(self):
        return json.dumps(
            self.db,
            cls=DecimalEncoder,
            separators=(',', ': '),
            indent=2
        )


class DecimalEncoder(json.JSONEncoder):
    def _iterencode(self, o, markers=None):
        if isinstance(o, float):
            return (str(o) for o in [o])
        return super(DecimalEncoder, self)._iterencode(o, markers)




