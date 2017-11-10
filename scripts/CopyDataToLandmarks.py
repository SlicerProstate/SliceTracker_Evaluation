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

# usage: Slicer --python-script CopyCaseDataToLandmarks.py -cr {ProstateCasesArchive} -ld {LandmarksOutputDirectory}

# Slicer --python-script CopyCaseDataToLandmarks.py -cr ~/Dropbox\ \(Partners\ HealthCare\)/ProstateBiopsyCasesArchive/ -ld ~/Dropbox\ \(Partners\ HealthCare\)/SliceTracker_Evaluation/Landmarks/

META_FILENAME = 'results.json'


def main(argv):

  # try:
  parser = argparse.ArgumentParser(description="Slicetracker Batch DeepLearning Segmentation")
  parser.add_argument("-cr", "--case-root-directory", dest="caseRootDir", metavar="PATH", default="-", required=True,
                      help="Root directory that holds cases")
  parser.add_argument("-ld", "--output-landmarks-directory", dest = "outputLandmarksDir", metavar = "PATH", default = "-", 
                      required = True,
                      help="Root directory of output holding sub directories named with case numbers")
  parser.add_argument("-d", "--debug", action='store_true')

  args = parser.parse_args(argv)

  if args.debug:
    slicer.app.layoutManager().selectModule("PyDevRemoteDebug")
    w = slicer.modules.PyDevRemoteDebugWidget
    w.connectButton.click()

  metafiles = []
  for root, dirs, files in os.walk(args.caseRootDir):
    metafiles = metafiles + [os.path.join(root, f) for f in files if META_FILENAME in f]

  data = {}

  for metafile in metafiles:
    caseNumber = re.search('/Case(.+?)-', metafile).group(1)
    if not os.path.exists(metafile):
      raise ValueError("Meta file %s does not exist" % metafile)
    try:
      data[caseNumber] = getData(metafile)
    except Exception:
      logging.warn("Errors while reading metafile %s" % metafile)
      continue

  # import pprint
  # pprint.pprint(data)

  copyData(data, args.outputLandmarksDir)
  sys.exit(0)


def getData(metafile):

  with open(metafile) as data_file:
    data = json.load(data_file)
    logging.debug("Reading metafile %s" % metafile)
    path = os.path.dirname(metafile)

    sortedResults = OrderedDict(sorted(data["results"].items(),
                                       key=lambda t: RegistrationResult.getSeriesNumberFromString(t[0])))

    # IMPORTANT: this code is for the OLD SliceTracker version 1.0!
    for index, (name, jsonResult) in enumerate(sortedResults.iteritems()):
      if jsonResult["status"] == RegistrationStatus.APPROVED_STATUS and "COVER PROSTATE" in name:
        return {
          # "preopVolume": os.path.join(path, jsonResult["movingVolume"]),
          "preopLabel": os.path.join(path, jsonResult["movingLabel"]),
          # "intraopVolume": os.path.join(path, jsonResult["fixedVolume"]),
          "intraopLabel": os.path.join(path, jsonResult["fixedLabel"]),
          "intraopTargets": os.path.join(path,
                                         jsonResult["targets"][jsonResult["approvedRegistrationType"]]),
          "transform": os.path.join(path,
                                    jsonResult["transforms"][jsonResult["approvedRegistrationType"]])
        }
  return None


def copyData(data, outputDir):

  for case, caseData in data.iteritems():
    if not caseData:
      continue
    outputCaseDir = os.path.join(outputDir, case)
    if not os.path.exists(outputCaseDir):
      print "%s does not exist" % case
      continue

    print "processing data of case %s" %case
    temp = os.path.join(outputCaseDir, "{}-PreopManual-label.nrrd".format(case))
    if not os.path.exists(temp):
      copy(caseData["preopLabel"], temp)

    temp = os.path.join(outputCaseDir, "{}-IntraopManual-label.nrrd".format(case))
    if not os.path.exists(temp):
      copy(caseData["intraopLabel"], temp)

    temp = os.path.join(outputCaseDir, "{}-Manual-transform.h5".format(case))
    if not os.path.exists(temp):
      copy(caseData["transform"], temp)
    # shutil.copy(caseData["intraopTargets"], os.path.join(outputCaseDir, "{}-IntraopTargets.fcsv".format(case)))


def copy(source, destination):
  print "Copying from %s to %s" % (source, destination)
  shutil.copy(source, destination)


if __name__ == "__main__":
  main(sys.argv[1:])

