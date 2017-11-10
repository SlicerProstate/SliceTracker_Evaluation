import os
import sys
import argparse
import slicer
import logging
import csv
from SlicerDevelopmentToolboxUtils.mixins import ModuleLogicMixin
from SliceTrackerUtils.sessionData import *

# usage: Slicer.exe --no-main-window --python-script CalculateTargetingSensitivity.py -ld {LandmarksDirectory}



validCases = [278,281,285,295,303,304,306,310,331,333,348,357,358,363,366,370,393,395,398,410,415,416,
              417,423,426,437,438,442,444,445,458,461,514,522,547,560,561,567,570,572,573,576,579,580]

def main(argv):

  try:
    parser = argparse.ArgumentParser(description="Targeting sensitivity calculator")
    parser.add_argument("-ld", "--landmark-root-directory", dest="landmarkRootDir", metavar="PATH", default="-", required=True,
                        help="Root directory that lists all cases holding information for landmarks")
    parser.add_argument("-o", "--output-file", dest="outputFile", metavar="PATH", default="-", required=True,
                        help="Output csv file")
    parser.add_argument("-tt", "--transform-type", dest="transformType", metavar="NAME", default="bSpline",
                        required=False, help="rigid|affine|bSpline")
    parser.add_argument("-d", "--debug", action='store_true')
    args = parser.parse_args(argv)

    if args.debug:
      slicer.app.layoutManager().selectModule("PyDevRemoteDebug")
      w = slicer.modules.PyDevRemoteDebugWidget
      w.connectButton.click()

    csvData = [['Case','Transformed_Target_Manual', 'Manual_Pos','Transformed_Target_Automatic','Automatic_Pos',
                'Target_Sensitivity']]

    csvData += getLandmarksLREs(args)

    csv_writer(csvData, os.path.join(args.landmarkRootDir, args.outputFile))

  except Exception, e:
    print e
  sys.exit(0)


def getLandmarksLREs(args):
  transformType = args.transformType

  data = []
  for root, dirs, _ in os.walk(args.landmarkRootDir):
    for case in dirs:
      if int(case) not in validCases:
        logging.info("Skipping case %s that is not in list of valid cases" % case)
        continue

      manualTargets = os.path.join(root, case, "{}-PreopTargets-transformed-{}-Manual.fcsv".format(case, transformType))
      automaticTargets = os.path.join(root, case, "{}-PreopTargets-transformed-{}-Automatic.fcsv".format(case, transformType))

      if all(os.path.exists(f) for f in [manualTargets, automaticTargets]):
        data += calculateLRE(case, manualTargets, automaticTargets)
      else:
        print "Data was not found for case %s" % case
  return data


def calculateLRE(case, landmark, transformed):
  success, landmarksNode = slicer.util.loadMarkupsFiducialList(landmark, returnNode=True)
  success, transformedNode = slicer.util.loadMarkupsFiducialList(transformed, returnNode=True)

  caseData = []
  for i in range(landmarksNode.GetNumberOfFiducials()):
    landmarkData = [case]

    landmarkPos = ModuleLogicMixin.getTargetPosition(landmarksNode, i)
    transformedPos = ModuleLogicMixin.getTargetPosition(transformedNode, i)
    landmarkTRE = ModuleLogicMixin.get3DEuclideanDistance(landmarkPos, transformedPos)

    landmarkData.append(landmarksNode.GetNthFiducialLabel(i))
    landmarkData.append(str(landmarkPos))
    landmarkData.append(transformedNode.GetNthFiducialLabel(i))
    landmarkData.append(str(transformedPos))
    landmarkData.append(landmarkTRE)

    caseData.append(landmarkData)

  return caseData


def getFiducialIndexByLabel(node, labelEnd):
  for index in range(node.GetNumberOfFiducials()):
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