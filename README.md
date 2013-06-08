## threeMaya

threeMaya is a simple Maya scene exporter for the three.js library.

currently support:
* mesh (no n-gons yet)
* uvs
* skinCluster skeleton
* skinCluster weights (reduced at 2 joints per vertex)
* skeleton animation (plot)

upcoming:
* materials
* vertex colors
* morph targets


# Installation

simply copy threeMaya.py into the folder of your choice from your PYTHONPATH
(your personal Maya scripts folder is a good start)


# How to run

```python
import threeMaya

e = threeMaya.Exporter('pCube1')
e.write('c:/work/three/anim_viewer/cube.js')
```
