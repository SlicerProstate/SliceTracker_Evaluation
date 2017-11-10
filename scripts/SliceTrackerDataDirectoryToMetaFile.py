import os
import sys
import logging
import re
import argparse
import json
from collections import OrderedDict

from SlicerDevelopmentToolboxUtils.mixins import ModuleLogicMixin

tempPath = '.'

def main(argv):

  parser = argparse.ArgumentParser(description="")
  parser.add_argument("-d", "--input-directory", dest="inputDirectory", metavar="PATH", default="-", required=True,
                      help="Input directory to parse into meta file")
  parser.add_argument("-o", "--output-meta-file", dest="outputFile", metavar="PATH", default="-", required=True,
                      help="Output file as json SliceTracker version 2.0")
  args = parser.parse_args(argv)

  assert os.path.exists(args.inputDirectory)

  # sort files by ##-

  # others are checked separately

  newData = {
    "results": []
  }

  print findTransformFromDataDirectory(args.inputDirectory)
  sys.exit(0)



def findTransformFromDataDirectory(directory):

  coverProstateFiles = [item for item in os.listdir(directory) if re.search('.?-T2-COVER-PROSTATE-.?', item)]

  if len (coverProstateFiles):
    seriesNumber = coverProstateFiles[0].split("-")[0]

  coverProstateFiles = [i for i in os.listdir(directory) if i.startswith("%s-" % seriesNumber)]

  # filter unapproved case first holding -approved
  suffix = ""

  targets = {}
  transforms = {}

  approvedTargets = None

  regTypes = ['rigid', 'affine', 'bSpline']

  for f in coverProstateFiles:
    if f.endswith("-approved.fcsv"):
      success, approvedTargets = slicer.util.loadMarkupsFiducialList(os.path.join(directory, f), returnNode=True)
    # elif any(regType in f for regType in regTypes):
    #   if "TARGETS" in f:
    #     targets[]
    #   elif "TRANSFORM" in f:
    elif f.endswith("-affine.fcsv"):
      targets["affine"] = os.path.join(directory, f)
    elif f.endswith("-bSpline.fcsv"):
      targets["bSpline"] = os.path.join(directory, f)
    elif f.endswith("-rigid.fcsv"):
      targets["rigid"] = os.path.join(directory, f)
    elif f.endswith("-affine.h5"):
      transforms["affine"] = os.path.join(directory, f)
    elif f.endswith("-bSpline.h5"):
      transforms["bSpline"] = os.path.join(directory, f)
    elif f.endswith("-rigid.h5"):
      transforms["rigid"] = os.path.join(directory, f)

  minDistance = None
  smallestDistanceType = None

  for regType, filepath in targets.iteritems():
    print filepath
    success, tempNode = slicer.util.loadMarkupsFiducialList(filepath, returnNode=True)

    distance = ModuleLogicMixin.get3DDistance(ModuleLogicMixin.getTargetPosition(tempNode, 0),
                                              ModuleLogicMixin.getTargetPosition(approvedTargets, 0))
    if not minDistance or distance < minDistance:
      minDistance = distance
      smallestDistanceType = regType

  if smallestDistanceType:
    print "Smallest distance to approved targets could be computed for type %s" % smallestDistanceType
    return transforms[smallestDistanceType]

  raise ValueError("Approved Cover Prostate transform could not be computed from parsing case directory!")


if __name__ == "__main__":
  main(sys.argv[1:])


