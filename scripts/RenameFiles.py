import os
import sys
import argparse
import shutil
import json
import logging
import re
import slicer
from collections import OrderedDict

from SliceTrackerUtils.sessionData import *

# usage: Slicer --python-script RenameFiles.py -ld {LandmarksOutputDirectory}

# Slicer --python-script RenameFiles.py -ld ~/Dropbox\ \(Partners\ HealthCare\)/SliceTracker_Evaluation/Landmarks/


def main(argv):

  # try:
  parser = argparse.ArgumentParser(description="Slicetracker Batch DeepLearning Segmentation")
  parser.add_argument("-ld", "--input-landmarks-directory", dest = "inputLandmarksDir", metavar = "PATH", default = "-", 
                      required = True,
                      help="Root directory of output holding sub directories named with case numbers")
  parser.add_argument("-d", "--debug", action='store_true')

  args = parser.parse_args(argv)

  if args.debug:
    slicer.app.layoutManager().selectModule("PyDevRemoteDebug")
    w = slicer.modules.PyDevRemoteDebugWidget
    w.connectButton.click()


  for root, dirs, files in os.walk(args.inputLandmarksDir):
    for case in dirs:
      absCaseDir = os.path.join(root, case)
      for f in os.listdir(absCaseDir):
        newName = None
        if "COVER PROSTATE" in f and f.endswith("-label.nrrd"):
          newName = "{}-IntraopManual-label.nrrd".format(case)
        elif "t2ax-label.nrrd" in f:
          newName = "{}-PreopManual-label.nrrd".format(case)
        elif any(name in f for name in ["T-BS.tfm", "Transform"]):
          newName = "{}-Manual-transform.tfm".format(case)
        elif "t2ax.nrrd" in f:
          os.remove(os.path.join(absCaseDir, f))
        if newName:
          print "renaming %s to %s" %(f, newName)
          shutil.move(os.path.join(absCaseDir, f), os.path.join(absCaseDir, newName))

  sys.exit(0)


if __name__ == "__main__":
  main(sys.argv[1:])

