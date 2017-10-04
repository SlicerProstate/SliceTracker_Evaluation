import os
import sys
import argparse
import json
import logging
import re
import slicer
from collections import OrderedDict
from SlicerDevelopmentToolboxUtils.mixins import ModuleLogicMixin
from SlicerDevelopmentToolboxUtils.constants import FileExtension
from SliceTrackerUtils.sessionData import *

# usage:  Slicer --no-main-window --python-script TransformPreopLandmarks.py -lr {LandmarksDirectory}
# -mcr {ProstateCasesArchive} -acr {AutomaticProstateSegmentationsCasesArchive}

# Slicer --no-main-window --python-script TransformPreopLandmarks.py -lr ~/Dropbox\ \(Partners\ HealthCare\)/SliceTracker_Evaluation/Landmarks/ -mcr ~/Dropbox\ \(Partners\ HealthCare\)/ProstateBiopsyCasesArchive/ -acr ~/Dropbox\ \(Partners\ HealthCare\)/SliceTracker_Evaluation/Segmentations/


def main(argv):

  try:
    parser = argparse.ArgumentParser(description="Slicetracker Transform Applicator")
    parser.add_argument("-lr", "--landmark-root-directory", dest="landmarkRootDir", metavar="PATH", default="-",
                        required=True, help="Root directory that lists all cases holding information for landmarks")
    parser.add_argument("-mcr", "--case-root-directory", dest="manualCaseRootDir", metavar="PATH", default="-",
                        required=True, help="Root directory that holds cases matching the numbers of landmark cases")
    parser.add_argument("-acr", "--automatic_segmentations-directory", dest="automaticCaseRootDir", metavar="PATH",
                        default="-", required=True,
                        help="Root directory that holds cases matching the numbers of landmark cases")
    args = parser.parse_args(argv)

    data = getPreopLandmarks(args)
    getManualTransformations(data, args)
    getAutomaticTransformations(data, args)
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


def getManualTransformations(data, args):

  metaFilePattern = 'results.json'

  caseNumbers = [c['case'] for c in data]
  outputDirs = [x[0] for x in os.walk(args.manualCaseRootDir) if 'MRgBiopsy' in x[0] and any("Case%s" % c in x[0] for c in caseNumbers)]

  for case in data:
    for outputDir in outputDirs:
      if "Case%s" % case['case'] in outputDir:
        metafile = os.path.join(outputDir, metaFilePattern)
        if not os.path.exists(metafile):
          raise ValueError("Meta file %s does not exist" %metafile)
        transform = getApprovedCoverProstateTransform(metafile)
        if transform:
          case['transformed_MANUAL'] = os.path.join(outputDir, transform)
        break


def getApprovedCoverProstateTransform(metafile):

  with open(metafile) as data_file:
    data = json.load(data_file)
    logging.debug("Reading metafile %s" % metafile)

    # print data["results"].keys()

    sortedResults = OrderedDict(sorted(data["results"].items(),
                                       key=lambda t: RegistrationResult.getSeriesNumberFromString(t[0])))

    # IMPORTANT: this code is for the OLD SliceTracker version 1.0!
    for index, (name, jsonResult) in enumerate(sortedResults.iteritems()):
      # TODO: think about "COVER-PROSTATE" in name because could be named differently, but should not be the case!
      if jsonResult["status"] == RegistrationStatus.APPROVED_STATUS and "COVER PROSTATE" in name:
        return jsonResult["transforms"][jsonResult["approvedRegistrationType"]]

    return None

    # print "No approved Cover Prostate found in %s. Searching data directory" % metafile
    # findTransformFromDataDirectory(os.path.dirname(metafile))

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


def getAutomaticTransformations(data, args):

  for case in data:
    path = os.path.join(args.automaticCaseRootDir, case['case'])

    if not os.path.exists(path):
      print "Path %s does not exist. Please check case %s" % (path, case['case'])
      continue

    regTypes = ['bSpline', 'affine', 'rigid']
    for regType in regTypes:
      if not os.path.join(path, "{}-VOLUME-{}{}".format(case['case'], regType, FileExtension.NRRD)):
        print "Skipping {0} transform of case {1} since there was no {0} volume produced".format(regType, case['case'])
        continue

      expectedFilePath = os.path.join(path, "{}-TRANSFORM-{}{}".format(case['case'], regType, FileExtension.H5))
      if not os.path.exists(expectedFilePath):
        print "Path %s does not exist. Please check case %s" % (expectedFilePath, case['case'])
      case['transformed_AUTOMATIC'] = expectedFilePath


def applyTransformations(data):

  for d in data:
    if not d.has_key('transformed_MANUAL'):
      print "No transform found for %s" % d['case']
      continue

    applyAndSaveTransform(d, 'transformed_MANUAL')
    applyAndSaveTransform(d, 'transformed_AUTOMATIC')

def applyAndSaveTransform(data, name):
    # print "loading transform from file %s" % data[name]
    success, transform = slicer.util.loadTransform(data[name], returnNode=True)
    success, preopLandmarks = slicer.util.loadMarkupsFiducialList(data['landmarks'], returnNode=True)

    ModuleLogicMixin.applyTransform(transform, preopLandmarks)

    print "saving to : %s/%s"  % (os.path.dirname(data['landmarks']), "{}-PreopLandmarks-{}".format(data['case'], name))

    ModuleLogicMixin.saveNodeData(preopLandmarks, os.path.dirname(data['landmarks']), FileExtension.FCSV,
                                  name="{}-PreopLandmarks-{}".format(data['case'], name))

if __name__ == "__main__":
  main(sys.argv[1:])

