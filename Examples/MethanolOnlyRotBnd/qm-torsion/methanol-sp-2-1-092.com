%RWF=/scratch/bdw2292/Gau-methanol/,200GB
%Nosave
%Chk=methanol-sp-2-1-092.chk
%Mem=100GB
%Nproc=8
#P wB97XD/6-311+G* SP SCF=(qc,maxcycle=800) Pop=NBORead MaxDisk=200GB 

methanol Rotatable Bond SP Calculation on node37.bme.utexas.edu

0 1
 O   -0.755785   -0.110495    0.004895
 C    0.659853    0.011517   -0.000329
 H    1.060137   -0.002793    1.024392
 H    0.984497    0.923897   -0.524158
 H    1.101136   -0.842057   -0.535396
 H   -1.138348    0.781149    0.022484

