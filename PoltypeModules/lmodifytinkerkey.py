import os
import shutil
import numpy as np
from rdkit import Chem
from openbabel import pybel

# this is to modify the intermediate tinker key files generated by poltype

""" special treatment for COO, when scaleandfixdipole is True """
def modkey2_COO(poltype):
  rdkitmol = Chem.MolFromMolFile(poltype.molstructfname,removeHs=False)
  scaleDipoleAtoms = []
  fixDipoleAtoms = []
  # acid or ester
  smt1 = "[C](=O)[O][#6,#1]" 
  # acetate anion 
  smt2 = "[C](=O)[O-]" 
  smts = [smt1, smt2]
  for smt in smts:
    pattern = Chem.MolFromSmarts(smt)
    match = rdkitmol.GetSubstructMatches(pattern)
    if match:
      for i in range(len(match)):	
        scaleDipoleAtoms += match[i][1:3]
        fixDipoleAtoms += match[i][0:3]
  
  # scale dipole of the atoms
  scaleDipoleRatio = 0.3
  atom2type = {}
  lines = open(poltype.xyzoutfile).readlines()
  for line in lines[1:]:
    ss = line.split()
    atom2type[int(ss[0])] = ss[5]

  scaleDipoleTypes = [atom2type[int(i)+1] for i in scaleDipoleAtoms]
  
  tmpkeyfile = poltype.key2fnamefromavg + '_tmp'
  lines = open(poltype.key2fnamefromavg).readlines()
  lines_append = []
  for atm in fixDipoleAtoms:
    lines_append.append(f"FIX-ATOM-DIPOLE {int(atm)+1} X\n")
    lines_append.append(f"FIX-ATOM-DIPOLE {int(atm)+1} Y\n")
    lines_append.append(f"FIX-ATOM-DIPOLE {int(atm)+1} Z\n")
  
  for i in range(len(lines)):
    line = lines[i]
    if ('multipole ' in line) and (line.split()[1] in scaleDipoleTypes):
      [dx, dy, dz] = lines[i+1].split()
      lines[i+1] = ' '*37 + f"{float(dx)*scaleDipoleRatio:10.5f}{float(dy)*scaleDipoleRatio:10.5f}{float(dz)*scaleDipoleRatio:10.5f}\n"
      
  with open(tmpkeyfile, 'w') as f:
    for line in lines:
      if "RESP-WEIGHT " in line:
        f.write(line)
        for apline in lines_append:
          f.write(apline)
          f.write(apline)
          f.write(apline)
      else:
        f.write(line)

  # rename key2 to key2b
  shutil.move(poltype.key2fnamefromavg, poltype.key2fnamefromavg+'b')
  # rename key2_tmp to key2
  shutil.move(poltype.key2fnamefromavg + '_tmp', poltype.key2fnamefromavg)
  return

""" this will be invoked when scalebigmultipole=True """
def modkey2_scalempole(poltype):
  key2 = poltype.key2fnamefromavg
  type2element = {}
  lines = open(key2).readlines()
  for line in lines:
    if 'atom ' in line:
      s = line.split()
      type2element[s[1]] = s[3].upper()
  
  # detect the big dipole and quadrupole and rewrite a keyfile
  blank = 34*' '
  mpole_lines = []
  with open('tmp_key_2', 'w') as f:
    for i in range(len(lines)):
      line = lines[i]
      if ("multipole " in line) and (line.split()[1] in type2element.keys()):
        current_type = line.split()[1]
        mpole_lines += [i, i+1, i+2, i+3, i+4]
        dx = float(lines[i+1].split()[-3])
        dy = float(lines[i+1].split()[-2])
        dz = float(lines[i+1].split()[-1])
        
        # modify dipole on-the-fly
        if (abs(dx) > 1.0 or abs(dy) > 1.0 or abs(dz) > 1.0) and (type2element[current_type] == 'C'):
          biggest = max([abs(dx), abs(dy), abs(dz)])
          ratio = biggest/0.5

          dx /= ratio
          dy /= ratio
          dz /= ratio

        qxx = float(lines[i+2].split()[-1])
        qyy = float(lines[i+3].split()[-1])
        qzz = float(lines[i+4].split()[-1])
        
        qxz = float(lines[i+4].split()[-3])
        qyz = float(lines[i+4].split()[-2])
        qxy = float(lines[i+3].split()[-2])
        
        # modify quadrupole on-the-fly
        if (abs(qxx) > 2.0 or abs(qyy) > 2.0 or abs(qzz) > 2.0) and (type2element[current_type] == 'C'):
          biggest = max([abs(qxx), abs(qyy), abs(qzz)])
          ratio = biggest/1.95

          qxx /= ratio
          qxy /= ratio
          qyy /= ratio
          qxz /= ratio
          qyz /= ratio
          qzz /= ratio
          poltype.WriteToLog(f"Scaling Down Big Quadrupoles for Atom Type {current_type}")
        
        # write multipole
        # charge
        f.write(line) 
        # dipole
        f.write(f"{blank}{dx:11.5f}{dy:11.5f}{dz:11.5f}\n")
        # quadrupole
        f.write(f"{blank}{qxx:11.5f}\n")
        f.write(f"{blank}{qxy:11.5f}{qyy:11.5f}\n")
        f.write(f"{blank}{qxz:11.5f}{qyz:11.5f}{qzz:11.5f}\n")
      else:
        if i not in mpole_lines:
          f.write(line)
  # rename key2 to key2b
  shutil.move(poltype.key2fnamefromavg, poltype.key2fnamefromavg+'b')
  # rename key2_tmp to key2
  shutil.move('tmp_key_2', poltype.key2fnamefromavg)
  return

""" this will be invoked when fragbigmultipole=True """
def modkey2_fragmpole(poltype):
  homedir = os.getcwd()
  key2 = poltype.key2fnamefromavg
  xyz2 = poltype.xyzoutfile
  sdf = poltype.molstructfname
  
  # Step 1: detect any atoms that have big multipoles
  atomsWithBigMultipole = []
  atomType2atomIndex = {}
  lines = open(xyz2).readlines()[1:]
  for line in lines:
    s = line.split()
    atomType = s[5]
    atomIndex = s[0]
    # only record the first atom for one type
    if atomType not in atomType2atomIndex.keys():
      atomType2atomIndex[atomType] = int(atomIndex)
      
  # there are default threshold values for c/d/q 
  # users can modify the keywords in poltype.ini

  charge_threshold = poltype.chargethreshold
  dipole_threshold = poltype.dipolethreshold
  quadrupole_threshold = poltype.quadrupolethreshold 
  
  max_charge = 0.0
  max_dipole = 0.0
  max_qdpole = 0.0
  
  rdkitmol = Chem.MolFromMolFile(sdf, removeHs=False)
  
  # only Carbon and Nitrogen
  allowed_elements = [6, 7]
  allowed_atomids = []
  for atom in rdkitmol.GetAtoms():
    atom_num = atom.GetAtomicNum()
    atom_id = atom.GetIdx()
    if atom_num in allowed_elements:
      allowed_atomids.append(atom_id + 1)
      
  lines = open(key2).readlines()
  for line in lines:
    if "multipole " in line:
      idx = lines.index(line)
      atomType = line.split()[1]
      atom_id = atomType2atomIndex[atomType]
      charge = float(line.split()[-1])
      if abs(charge) > max_charge:
        max_charge = abs(charge)
      if abs(charge) > charge_threshold:
        if (atom_id not in atomsWithBigMultipole) and (atom_id in allowed_atomids):
          atomsWithBigMultipole.append(atom_id)
      for dipole in lines[idx+1].split():
        if abs(float(dipole)) > max_dipole:
          max_dipole = abs(float(dipole))

        if abs(float(dipole)) > dipole_threshold:
          if (atom_id not in atomsWithBigMultipole) and (atom_id in allowed_atomids):
            atomsWithBigMultipole.append(atom_id)
      for qpline in lines[idx+2:idx+5]:
        quadrupoles = qpline.split()
        for quadrupole in quadrupoles:
          if abs(float(quadrupole)) > max_qdpole:
            max_qdpole =  abs(float(quadrupole))

          if abs(float(quadrupole)) > quadrupole_threshold:
            if (atom_id not in atomsWithBigMultipole) and (atom_id in allowed_atomids):
              atomsWithBigMultipole.append(atom_id)
  
  # Step 2: generate the "best" fragment and run poltype job
  # use an external program, lFragmenterForDMA.py, to do this
  # it can be run directly without involking poltype job
  
  if poltype.atomidsfordmafrag != []:
    poltype.WriteToLog(f"User Inputed Atoms for Fragmentation: {' '.join([str(i) for i in poltype.atomidsfordmafrag])}")
    poltype.WriteToLog("!!! Poltype will NOT Detect BIG Multipoles !!!")
    atomsWithBigMultipole = poltype.atomidsfordmafrag

  if atomsWithBigMultipole != []:
    poltype.WriteToLog(f"Atoms with BIG multipole: {' '.join([str(i) for i in atomsWithBigMultipole])}")
    os.system('mkdir -p Fragments_DMA')
    os.chdir(os.path.join(homedir, 'Fragments_DMA'))
    for atom_idx in atomsWithBigMultipole:
      cmdstr = f"python \"{os.path.join(os.path.abspath(os.path.split(__file__)[0]), 'lFragmenterForDMA.py')}\" {homedir}/{sdf} {atom_idx}"
      poltype.WriteToLog('Calling: '+cmdstr) 
      os.system(cmdstr)
    
    fragment_jobs = [] 
    files = os.listdir()
    for f in files:
      os.chdir(os.path.join(homedir, 'Fragments_DMA'))
      if f.startswith('Frag_Atom') and os.path.isfile(f):
        fname = f.split('.mol')[0]
        os.system(f'mkdir -p {fname}')
        os.system(f'mv {f} ./{fname}')
        with open(f"./{fname}/poltype.ini", 'w') as pt:
          pt.write(f"structure={f}\n")
          pt.write("dontdotor\n")
          pt.write("espbasisset=6-311G**\n")
          pt.write("sameleveldmaesp=True\n")
          pt.write("scalebigmultipole=True\n")
          pt.write(f"numproc={poltype.numproc}\n")
          pt.write(f"maxmem={poltype.maxmem}\n")
          pt.write(f"maxdisk={poltype.maxdisk}\n")
        
        # Run Poltype Job
        os.chdir(os.path.join(homedir, 'Fragments_DMA', fname))
        cmdstr='python'+' '+ os.path.join(poltype.poltypepath, 'poltype.py')
        poltype.call_subsystem([cmdstr], True)
        fragment_jobs.append(fname)

    # Step 3: transfer the multipoles back to parent molecules
    os.chdir(homedir)
    
    # make a copy of the parent key to work on
    os.system(f'cp {key2} tmpkeyforfrag.key')

    parent_key = "tmpkeyforfrag.key"
    parent_sdf = sdf
    parent_xyz = xyz2
    for fragment_job in fragment_jobs:
      frag_dir = os.path.join(homedir, 'Fragments_DMA', fragment_job)
      frag_sdf = os.path.join(frag_dir, f'{fragment_job}.mol')
      frag_xyz = os.path.join(frag_dir, 'final.xyz')
      frag_key = os.path.join(frag_dir, 'final.key')
      
      transferMultipoleToParent(poltype, frag_sdf, frag_xyz, frag_key, parent_sdf, parent_xyz, parent_key)
    
    shutil.move(key2, key2+'_noFrag')
    shutil.move('tmpkeyforfrag.key', key2)
  return

# helper function to transfer multipole back to parent
def transferMultipoleToParent(poltype, frag_sdf, frag_xyz, frag_key, parent_sdf, parent_xyz, parent_key):

  fragment2parentatom = {}

  # get atom2type for parent molecule
  parentatom2type = {}
  lines = open(parent_xyz).readlines()[1:]
  for line in lines:
    s = line.split()
    parentatom2type[s[0]] = s[5]
    parentatom2type[f'-{s[0]}'] = f'-{s[5]}'
  

  # match geometry of fragment and parent mols
  ## get frag xyz2index
  frag_mol = Chem.MolFromMolFile(frag_sdf, removeHs=False)
  frag_xyz2index = {}
  for atom in frag_mol.GetAtoms():
    atom_idx = atom.GetIdx()
    coord = frag_mol.GetConformer().GetAtomPosition(atom_idx) 
    x, y, z = f"{coord.x:10.4f}", f"{coord.y:10.4f}", f"{coord.z:10.4f}"
    xyzstr = ''.join([x,y,z])
    frag_xyz2index[xyzstr] = atom_idx
  
  ## get par xyz2index
  par_mol = Chem.MolFromMolFile(parent_sdf, removeHs=False)
  par_xyz2index = {}
  for atom in par_mol.GetAtoms():
    atom_idx = atom.GetIdx()
    coord = par_mol.GetConformer().GetAtomPosition(atom_idx) 
    x, y, z = f"{coord.x:10.4f}", f"{coord.y:10.4f}", f"{coord.z:10.4f}"
    xyzstr = ''.join([x,y,z])
    par_xyz2index[xyzstr] = atom_idx

  ## construct fragment2parentatom dictionary
  for key, value in par_xyz2index.items():
    if key in frag_xyz2index.keys():
      value_frag = frag_xyz2index[key]
      fragment2parentatom[value_frag] = value

  # construct heavyatomlist to transfer charge
  frag_heavyatoms = []
  for line in open(frag_xyz).readlines()[1:]:
    s = line.split()
    if (s[1].upper() != 'H') and (int(s[0]) - 1 in fragment2parentatom.keys()):
      frag_heavyatoms.append(s[0])
  par_heavyatoms = [str(fragment2parentatom[int(a)-1] + 1) for a in frag_heavyatoms]

  # run analyze to get multipoles
  cmdstr = f"{poltype.analyzeexe} {frag_xyz} -k {frag_key} EP > frag_ana.log; wait"
  os.system(cmdstr)
  cmdstr = f"{poltype.analyzeexe} {parent_xyz} -k {parent_key} EP > parent_ana.log; wait"
  os.system(cmdstr)

  # read frag_ana.log
  lines = open('frag_ana.log').readlines()
  
  key_str = 'Atomic Multipole Parameters :'
  
  ## key_str first appears with atom type
  ## key_str later appears with atom number
  ## here we use the second one as starting index
  for line in lines:
    if (key_str in line):
      mpole_idx = lines.index(line)
 
  ## construct par_newmultipole dictionary
  ## accumulate total charge on frag atoms
  frag_totalcharge = 0.0
  par_atom2newmultipole = {}
  for i in range(mpole_idx + 4, len(lines), 5):
    s = lines[i].split()
    if len(s) == 0:break
    frame_name = s[-2]
    ## AMOEBA multipole has 6 local frames
    if frame_name in ['Z-then-X', 'Bisector', '3-Fold', 'Z-Bisect', 'None', 'Z-Only']:
      # None: 1 1 None 0.10000
      # Only charge is transferred
      if (frame_name == 'None'):
        atom = s[0]
        par_atom = str(fragment2parentatom[int(atom) - 1] + 1)
        frame = []
        charge = [s[-1]]
        frag_totalcharge += float(charge[0])
        dipoles = []
        quadrupoles = []
        par_atom2newmultipole[par_atom] = [frame, charge, dipoles, quadrupoles]
      
      # Z-Only: 1 1 2 Z-Only 0.10000
      if (frame_name == 'Z-Only'):
        atom = s[0]
        a1 = int(s[2]) - 1
        
        if (atom in frag_heavyatoms):
          par_atom = str(fragment2parentatom[int(atom) - 1] + 1)
          if (a1 in fragment2parentatom):
            a1_par = str(fragment2parentatom[a1] + 1)
            frame = [f' {a1_par}']
            charge = [s[-1]]
            frag_totalcharge += float(charge[0])
            dipoles = [lines[i+1]]
            quadrupoles = [lines[i+2], lines[i+3], lines[i+4]]
            par_atom2newmultipole[par_atom] = [frame, charge, dipoles, quadrupoles]
          else:
            frame = []
            charge = [s[-1]]
            frag_totalcharge += float(charge[0])
            dipoles = []
            quadrupoles = []
            par_atom2newmultipole[par_atom] = [frame, charge, dipoles, quadrupoles]

      # Z-then-X: 1 1 2 3 Z-then-X 0.10000 
      # Bisector: 1 1 2 3 Bisector 0.10000 
      if (frame_name == 'Z-then-X') or (frame_name == 'Bisector'):
        atom = s[0]
        a1 = int(s[2]) - 1
        a2 = int(s[3]) - 1
        
        if (atom in frag_heavyatoms):
          par_atom = str(fragment2parentatom[int(atom) - 1] + 1)
          if (a1 in fragment2parentatom) and (a2 in fragment2parentatom):
            a1_par = str(fragment2parentatom[a1] + 1)
            a2_par = str(fragment2parentatom[a2] + 1)
            if (frame_name == 'Z-then-X'):
              frame = [' '.join([a1_par, a2_par])]
            if (frame_name == 'Bisector'):
              frame = [' '.join([f'-{a1_par}', f'-{a2_par}'])]
            charge = [s[-1]]
            frag_totalcharge += float(charge[0])
            dipoles = [lines[i+1]]
            quadrupoles = [lines[i+2], lines[i+3], lines[i+4]]
            par_atom2newmultipole[par_atom] = [frame, charge, dipoles, quadrupoles]
          else:
            frame = []
            charge = [s[-1]]
            frag_totalcharge += float(charge[0])
            dipoles = []
            quadrupoles = []
            par_atom2newmultipole[par_atom] = [frame, charge, dipoles, quadrupoles]
            
      # 3-Fold: 1 1 2 3 4 3-Fold 0.10000 
      # Z-Bisect: 1 1 2 3 4 Z-Bisect 0.10000 
      if (frame_name == '3-Fold') or (frame_name == 'Z-Bisect'):
        atom = s[0]
        a1 = int(s[2]) - 1
        a2 = int(s[3]) - 1
        a3 = int(s[4]) - 1

        if (atom in frag_heavyatoms):
          par_atom = str(fragment2parentatom[int(atom) - 1] + 1)
          if (a1 in fragment2parentatom) and (a2 in fragment2parentatom) and (a3 in fragment2parentatom):
            a1_par = str(fragment2parentatom[a1] + 1)
            a2_par = str(fragment2parentatom[a2] + 1)
            a3_par = str(fragment2parentatom[a3] + 1)
            if (frame_name == '3-Fold'):
              frame = [' '.join([f'-{a1_par}', f'-{a2_par}', f'-{a3_par}'])]
            if (frame_name == 'Z-Bisect'): 
              frame = [' '.join([a1_par, f'-{a2_par}', f'-{a3_par}'])]
            charge = [s[-1]]
            frag_totalcharge += float(charge[0])
            dipoles = [lines[i+1]]
            quadrupoles = [lines[i+2], lines[i+3], lines[i+4]]
            par_atom2newmultipole[par_atom] = [frame, charge, dipoles, quadrupoles]
          else:
            frame = []
            charge = [s[-1]]
            frag_totalcharge += float(charge[0])
            dipoles = []
            quadrupoles = []
            par_atom2newmultipole[par_atom] = [[], charge, dipoles, quadrupoles]

  # read parent_ana.log
  lines = open('parent_ana.log').readlines()
  for line in lines:
    if ('Atomic Multipole Parameters :' in line):
      mpole_idx = lines.index(line)
  ## accumulate total charge on parent atoms
  parent_totalcharge = 0.0
  for i in range(mpole_idx + 4, len(lines), 5):
    s = lines[i].split()
    if len(s) == 0:break
    if s[0] in par_atom2newmultipole.keys():
      charge = s[-1]
      parent_totalcharge += float(charge)

  charge_diff = parent_totalcharge - frag_totalcharge
  charge_peratom = charge_diff/len(frag_heavyatoms)
  
  ## write the amount of re-distributed charge to log
  poltype.WriteToLog(f"Re-distributed Charge Per Atom: {charge_peratom:.5f}")
  ## charge redistribute
  ## check total charge again on parent atoms
  parent_totalcharge_1 = 0.0
  for atom in par_heavyatoms:
    v = par_atom2newmultipole[atom]
    v[1] = [f"{(float(v[1][0]) + charge_peratom):.5f}"]
    par_atom2newmultipole[atom] = v
    parent_totalcharge_1 += float(v[1][0])
  
  # construct type2multipole dictionary
  par_type2multipole = {}

  for atom,v in par_atom2newmultipole.items():
    atype = parentatom2type[atom]
    frame = '   '.join(parentatom2type[a] for a in v[0][0].split())
    charge = v[1][0]
    dipole = v[2][0]
    quadrupole = '   '.join(v[3])
    
    if atype not in par_type2multipole.keys():
      par_type2multipole[atype] = f'multipole {atype} {frame} {charge}\n{dipole}{quadrupole}'
    else:
      # in this case there are equavalent atoms
      # already satistified, so just pass
      pass
      
  ## write the new key with new multipoles
  lines = open(parent_key).readlines()
  mpole_lines = []
  with open('tmpkeyforfrag.key', 'w') as f:
    for i in range(len(lines)):
      line = lines[i]
      if ('multipole ' in line) and (line.split()[1] in par_type2multipole.keys()): 
        mpole_lines += [i, i+1, i+2, i+3, i+4]

      # write to file
      if i not in mpole_lines:
        f.write(line)
      else:
        if  ('multipole ' in line):
          atype = line.split()[1]
          f.write(par_type2multipole[atype])
  return

# here we write any modifications to the final.key
def mod_final_key(poltype):
  xyz = poltype.tmpxyzfile
  key = poltype.tmpkeyfile
  sdf = poltype.molstructfname
  prmfiledir = poltype.ldatabaseparserprmdir
  # Match special polpair values
  # these are usually tough cases
  atomnumbers, types = np.loadtxt(xyz, usecols=(0, 5,), unpack=True, dtype="str", skiprows=1)
  atomnumbers = [int(a) for a in atomnumbers]
  atom_type_dict = dict(zip(atomnumbers, types)) 
  prmlines = open(os.path.join(prmfiledir,"amoebaPolarPair.prm")).readlines()
  # SDF is more info-rich 
  inpfile = sdf
  inpformat = 'sdf'
  
  # try to match line-by-line
  matched_polpairs = []
  comments = []
  tmp = []
  for mol in pybel.readfile(inpformat,inpfile):
    for line in prmlines:
      if ("#" not in line[0]) and (len(line) > 10):
        s = line.split()
        smt = s[0]
        polpair_params = '   '.join(s[2:5])
        polpair_comment = ' '.join(s[6:])
        smarts = pybel.Smarts(smt)
        matches = smarts.findall(mol)
        if matches != []:
          for match in matches:
            a = match[0] 
            polpair_type = atom_type_dict[a] 
            if (polpair_type not in tmp):
              tmp.append(polpair_type)
              polpair_prm_str = f"polpair {polpair_type} {polpair_params}"
              matched_polpairs.append(polpair_prm_str)
              comments.append(polpair_comment)

  idx = -1 
  keylines = open(key).readlines()
  for line in keylines:
    if 'polarize ' in line:
      idx = keylines.index(line)
  
  # write the matched polpair parameters 
  with open(key, "w") as f:
    for i in range(len(keylines)):
      line = keylines[i]
      if i != idx:
        f.write(line)
      else:
        f.write(line)
        if matched_polpairs != []:
          for c, p in zip(comments, matched_polpairs):
            f.write(f"# {c}\n")
            f.write(f"{p}\n")
  return
