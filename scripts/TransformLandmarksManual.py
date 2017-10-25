import os
import sys
import argparse
import logging
import slicer
from SlicerDevelopmentToolboxUtils.mixins import ModuleLogicMixin
from SlicerDevelopmentToolboxUtils.constants import FileExtension
from SliceTrackerUtils.sessionData import *

# usage:  Slicer --no-main-window --python-script TransformLandmarksManual.py -ld {LandmarksDirectory}

# Slicer --no-main-window --python-script TransformLandmarksManual.py -ld ~/Dropbox\ \(Partners\ HealthCare\)/SliceTracker_Evaluation/Landmarks/

def main(argv):

  try:
    parser = argparse.ArgumentParser(description="Slicetracker Transform Applicator")
    parser.add_argument("-ld", "--landmark-root-directory", dest="landmarkRootDir", metavar="PATH", default="-",
                        required=True, help="Root directory that lists all cases holding information for landmarks")
    args = parser.parse_args(argv)

    for root, dirs, _ in os.walk(args.landmarkRootDir):
      for case in dirs:
        absCaseDir = os.path.join(root, case)

        landmarks = None
        transform = None
        for currentFile in os.listdir(absCaseDir):
          if currentFile == "{}-PreopLandmarks.fcsv".format(case):
            landmarks = os.path.join(root, case, currentFile)
          elif currentFile in ["{}-Manual-transform.tfm".format(case), "{}-Manual-transform.h5".format(case)]:
            transform = os.path.join(root, case, currentFile)

        if landmarks and transform:
          logging.info("Did not found landmarks/transforms for case %s" % case)

          success, transformNode = slicer.util.loadTransform(transform, returnNode=True)
          success, landmarksNode = slicer.util.loadMarkupsFiducialList(landmarks, returnNode=True)
          ModuleLogicMixin.applyTransform(transformNode, landmarksNode)

          fileName = "{}-PreopLandmarks-transformed_MANUAL".format(case)

          print "saving to : %s/%s" % (os.path.dirname(landmarks), fileName)

          ModuleLogicMixin.saveNodeData(landmarksNode, os.path.dirname(landmarks), FileExtension.FCSV, name=fileName)
        else:
          logging.warn("Did not found landmarks/transforms for case %s" % case)


  except Exception, e:
    print e
  sys.exit(0)



if __name__ == "__main__":
  main(sys.argv[1:])

