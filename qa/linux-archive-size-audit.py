#!/usr/bin/env python3
"""Read-only tar member inventory; report actual uncompressed sizes."""
import collections, hashlib, pathlib, sys, tarfile
testdir,olddir=map(pathlib.Path,sys.argv[1:3])
def group(n):
 p=n.lstrip("./"); name=p.split("/")[-1]
 if p.startswith("lib/"):
  if name.startswith("libQt5"):return "Qt5 shared libs"
  if name.startswith(("libssl","libcrypto")):return "OpenSSL shared libs"
  return "Other shared libs"
 if p.startswith("plugins/"):return "Qt plugins"
 if name in ("PEPEPOW_qt","PEPEPOWd","PEPEPOW-cli","PEPEPOW-tx"):return name
 if p.startswith("bin/"):return "headless bin/"
 return "Other content"
for label,d in (("v2.9.0.6-test",testdir),("v2.9.0.5-official",olddir)):
 archives=sorted(d.glob("*-linux-gnu.tgz"))
 if not archives:print(f"{label}: no archives available")
 for t in archives:
  with tarfile.open(t,"r:gz") as arc:
   files=[m for m in arc.getmembers() if m.isfile()]
  sections=collections.Counter(); counts=collections.Counter()
  for m in files:
   sections[group(m.name)]+=m.size;counts[group(m.name)]+=1
  print(f"\n### {label}: {t.name}")
  print(f"Compressed {t.stat().st_size/1048576:.2f} MiB; uncompressed {sum(m.size for m in files)/1048576:.2f} MiB; members {len(files)}")
  for k,v in sections.most_common(): print(f"GROUP {k:24s} {v/1048576:8.2f} MiB ({counts[k]} files)")
  for m in sorted(files,key=lambda m:m.size,reverse=True)[:35]:
   print(f"FILE  {m.size/1048576:8.2f} MiB {m.name}")
