import os
import sys
import argparse
import json
import logging
import slicer
from collections import OrderedDict
from SlicerDevelopmentToolboxUtils.mixins import ModuleLogicMixin
from SlicerDevelopmentToolboxUtils.constants import FileExtension
from SliceTrackerUtils.sessionData import *

# usage:  Slicer --no-main-window --python-script TransformPreopLandmarks.py -lr {LandmarksDirectory} -cr {ProstateCasesArchive}


def main(argv):

  try:
    parser = argparse.ArgumentParser(description="Slicetracker Transform Applicator")
    parser.add_argument("-lr", "--landmark-root-directory", dest="landmarkRootDir", metavar="PATH", default="-", required=True,
                        help="Root directory that lists all cases holding information for landmarks")
    parser.add_argument("-cr", "--case-root-directory", dest="caseRootDir", metavar="PATH", default="-", required=True,
                        help="Root directory that holds cases matching the numbers of landmark cases")
    args = parser.parse_args(argv)

    data = getPreopLandmarks(args)
    getTransformations(data, args)

    applyTransformations(data)

  except Exception, e:
    print e
  sys.exit(0)


def getPreopLandmarks(args):

  data = []
  for root, dirs, _ in os.walk(args.landmarkRootDir):
    for landmarkDir in dirs:
      for currentFile in os.listdir(os.path.join(root, landmarkDir)):
        if '-PreopLandmarks.fcsv' in currentFile:
          absLandmarkPath = os.path.join(root, landmarkDir, currentFile)

          data.append({
            'case': landmarkDir,
            'landmarks': absLandmarkPath
          })
  return data


def getTransformations(data, args):

  metaFilePattern = 'results.json'

  caseNumbers = [c['case'] for c in data]
  outputDirs = [x[0] for x in os.walk(args.caseRootDir) if 'MRgBiopsy' in x[0] and any("Case%s" % c in x[0] for c in caseNumbers)]

  for case in data:
    for outputDir in outputDirs:
      if "Case%s" % case['case'] in outputDir:
        metafile = os.path.join(outputDir, metaFilePattern)
        if not os.path.exists(metafile):
          raise ValueError("Meta file %s does not exist" %metafile)
        case['transform'] = os.path.join(outputDir, getApprovedCoverProstateTransform(metafile))
        break


def getApprovedCoverProstateTransform(metafile):

  with open(metafile) as data_file:
    data = json.load(data_file)
    logging.debug("Reading metafile %s" % metafile)

    # print data["results"].keys()

    sortedResults = OrderedDict(sorted(data["results"].items()))

    # IMPORTANT: this code is for the OLD SliceTracker version 1.0!
    for index, (name, jsonResult) in enumerate(sortedResults.iteritems()):
      if jsonResult["status"] == RegistrationStatus.APPROVED_STATUS:
        return jsonResult["transforms"][jsonResult["approvedRegistrationType"]]

  return None


def applyTransformations(data):

  for d in data:
    success, transform = slicer.util.loadTransform(d['transform'], returnNode=True)
    success, preopLandmarks = slicer.util.loadMarkupsFiducialList(d['landmarks'], returnNode=True)

    ModuleLogicMixin.applyTransform(transform, preopLandmarks)


    print "saving to : %s"  % os.path.dirname(d['landmarks'])

    ModuleLogicMixin.saveNodeData(preopLandmarks, os.path.dirname(d['landmarks']), FileExtension.FCSV,
                                  name="{}-PreopLandmarks-transformed".format(d['case']))

if __name__ == "__main__":
  main(sys.argv[1:])

