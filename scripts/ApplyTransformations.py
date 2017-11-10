import os
import sys
import argparse
import logging
import slicer
from SlicerDevelopmentToolboxUtils.mixins import ModuleLogicMixin
from SlicerDevelopmentToolboxUtils.constants import FileExtension
from SliceTrackerUtils.sessionData import *

# usage:  Slicer --no-main-window --python-script ApplyTransformations.py -ld {LandmarksDirectory}

# Slicer --no-main-window --python-script ApplyTransformations.py -ld ~/Dropbox\ \(Partners\ HealthCare\)/SliceTracker_Evaluation/Landmarks/ -tt Manual

def main(argv):

  try:
    parser = argparse.ArgumentParser(description="Slicetracker Transform Applicator")
    parser.add_argument("-ld", "--landmark-root-directory", dest="landmarkRootDir", metavar="PATH", default="-",
                        required=True, help="Root directory that lists all cases holding information for landmarks")
    parser.add_argument("-st", "--segmentation-type", dest="segmentationType", metavar="NAME", default="-",
                        choices=['Manual', 'Automatic'], required=True, help="Expected transform name will be "
                                                 "{casenumber}-TRANSFORM-{transformType}-{segmentationType}.h5")
    parser.add_argument("-tt", "--transform-type", dest="transformType", metavar="NAME", default="-",
                        choices=['rigid', 'affine', 'bSpline'], required=True,
                        help="%(choices). expected transform name: {casenumber}-TRANSFORM-{transformType}-{segmentationType}.h5")
    parser.add_argument("-ft", "--fiducial-type", dest="fiducialType", metavar="NAME", default="-", choices = ['Targets', 'Landmarks'],
                        required=True, help='list servers, storage, or both (default: %(default)s)')

    args = parser.parse_args(argv)

    segmentationType = args.segmentationType
    transformType = args.transformType
    fiducialType = args.fiducialType

    for root, dirs, _ in os.walk(args.landmarkRootDir):
      for case in dirs:
        landmarks = os.path.join(root, case, "{}-Preop{}.fcsv".format(case, fiducialType))
        transform = os.path.join(root, case, "{}-TRANSFORM-{}-{}.h5".format(case, transformType, segmentationType))

        # check if exists and if is identity
        volume = os.path.join(root, case, "{}-VOLUME-{}-{}.nrrd".format(case, transformType, segmentationType))
        if not os.path.exists(volume):
          logging.info("Case {}: No valid {} transform found.Falling back to affine".format(case, transformType))
          # volume = os.path.join(root, case, "{}-VOLUME-affine-{}.nrrd".format(case, segmentationType))
          transform = os.path.join(root, case, "{}-TRANSFORM-affine-{}.h5".format(case, segmentationType))

        if all(os.path.exists(f) for f in [landmarks, transform]):
          success, landmarksNode = slicer.util.loadMarkupsFiducialList(landmarks, returnNode=True)
          success, transformNode = slicer.util.loadTransform(transform, returnNode=True)
          ModuleLogicMixin.applyTransform(transformNode, landmarksNode)

          fileName = "{}-Preop{}-transformed-{}-{}".format(case, fiducialType, transformType, segmentationType)

          print "saving to : {}/{}{}".format(os.path.dirname(landmarks), fileName, FileExtension.FCSV)

          ModuleLogicMixin.saveNodeData(landmarksNode, os.path.dirname(landmarks), FileExtension.FCSV, name=fileName)
        else:
          logging.warn("Did not find landmarks/transforms for case %s" % case)



  except Exception, e:
    print e
  sys.exit(0)



if __name__ == "__main__":
  main(sys.argv[1:])

