import os
import sys
import argparse
import slicer
import csv
from SlicerDevelopmentToolboxUtils.mixins import ModuleLogicMixin
from SliceTrackerUtils.sessionData import *

# usage:  Slicer.exe --no-main-window --python-script CalculateLandmarkRegistrationError.py -lr {LandmarksDirectory}


def main(argv):

  try:
    parser = argparse.ArgumentParser(description="Slicetracker Transform Applicator")
    parser.add_argument("-lr", "--landmark-root-directory", dest="landmarkRootDir", metavar="PATH", default="-", required=True,
                        help="Root directory that lists all cases holding information for landmarks")
    args = parser.parse_args(argv)

    data = getLandmarks(args)
    dataHeader = ['Case','Label', 'Intraop x-pos', 'Intraop y-pos', 'Intraop z-pos', 'PreopTransformed Label',
               'PreopTransformed x-pos', 'PreopTransformed y-pos', 'PreopTransformed z-pos', " ", 'LRE-Fiducial',
               'LRE-Case', 'LRE-Total']
    csvData = [dataHeader]
    totalLRE = 0

    for case in data:
      csvData.append([case['case']])
      caseData = calculateLRE(case)
      totalLRE = totalLRE + caseData[-1][-1]
      for list in caseData:
        csvData.append(list)
      csvData.append([""])

    totalLRE = totalLRE / (len(data) * 1.0)
    csvData.append(["","","","","","","","","","","","",totalLRE])
    csv_writer(csvData, args.landmarkRootDir+'\LREOutput.csv')

  except Exception, e:
    print e
  sys.exit(0)


def getLandmarks(args):
  data = []
  for root, dirs, _ in os.walk(args.landmarkRootDir):
    for landmarkDir in dirs:
      files = os.listdir(os.path.join(root, landmarkDir))
      for currentFile in files:
        if '-IntraopLandmarks.fcsv' in currentFile:
          absIntraopLandmarkPath = os.path.join(root, landmarkDir, currentFile)
        elif '-PreopLandmarks-transformed.fcsv' in currentFile:
          absPreopTransformedLandmarkPath = os.path.join(root, landmarkDir, currentFile)
      data.append({
        'case': landmarkDir,
        'intraopLandmarks': absIntraopLandmarkPath,
        'preopTransformedLandmarks': absPreopTransformedLandmarkPath
      })
  return data

def calculateLRE(case):
  success, intraopLandmarks = slicer.util.loadMarkupsFiducialList(case['intraopLandmarks'], returnNode=True)
  success, preopTransformedLandmarks = slicer.util.loadMarkupsFiducialList(case['preopTransformedLandmarks'], returnNode=True)
  numLandmarks = intraopLandmarks.GetNumberOfFiducials()
  caseData = []
  caseTRE = 0

  for i in range(numLandmarks):
    label = preopTransformedLandmarks.GetNthFiducialLabel(i)
    label = "-" + label.split("-")[-1]
    fiducialIndex = getFiducialIndexByLabel(intraopLandmarks, label)
    intraopPos = ModuleLogicMixin.getTargetPosition(intraopLandmarks, fiducialIndex)
    preopTransformedPos = ModuleLogicMixin.getTargetPosition(preopTransformedLandmarks, i)
    landmarkTRE = ModuleLogicMixin.get3DEuclideanDistance(intraopPos, preopTransformedPos)
    caseTRE = caseTRE + landmarkTRE
    caseData.append([" ", intraopLandmarks.GetNthFiducialLabel(fiducialIndex), intraopPos[0], intraopPos[1], intraopPos[2],
                     preopTransformedLandmarks.GetNthFiducialLabel(i), preopTransformedPos[0], preopTransformedPos[1],
                     preopTransformedPos[2], "", landmarkTRE])

  caseTRE = caseTRE / (numLandmarks * 1.0)
  caseData.append(["","","","","","","","","","","",caseTRE])

  return caseData

def getFiducialIndexByLabel(node, labelEnd):
  for index in range(node.GetNumberOfFiducials()):
    print index
    print node.GetNthFiducialLabel(index)
    if node.GetNthFiducialLabel(index).endswith(labelEnd):
      return index
  return -1

def csv_writer(data, path):
  """
  Write data to a CSV file path
  """
  with open(path, "wb") as csv_file:
    writer = csv.writer(csv_file, delimiter=',')
    for line in data:
      writer.writerow(line)


if __name__ == "__main__":
  main(sys.argv[1:])