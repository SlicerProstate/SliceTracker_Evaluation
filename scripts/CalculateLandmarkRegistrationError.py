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
    parser.add_argument("-d", "--debug", action='store_true')
    args = parser.parse_args(argv)

    if args.debug:
      slicer.app.layoutManager().selectModule("PyDevRemoteDebug")
      w = slicer.modules.PyDevRemoteDebugWidget
      w.connectButton.click()


    csvData = [['Case','Label', 'Intraop x-pos', 'Intraop y-pos', 'Intraop z-pos', '',
                'PreopTransformed Label manually','x-pos', 'y-pos', 'z-pos', 'LRE-Fiducial', 'LRE-Case', 'LRE-Total', '',
                'PreopTransformed Label automatic', 'x-pos', 'y-pos', 'z-pos', 'LRE-Fiducial', 'LRE-Case', 'LRE-Total', '']]


    data = getLandmarks(args)
    manualTotalLRE = 0.0
    automaticTotalLRE = 0.0
    for case in data:
      csvData.append([case['case']])
      caseData = calculateLRE(case)
      manualTotalLRE += caseData['manualCaseTRE']
      automaticTotalLRE += caseData['automaticCaseTRE']
      for list in caseData['data']:
        csvData.append(list)
      csvData.append([""])

    manualTotalLRE /= (len(data) * 1.0)
    automaticTotalLRE /= (len(data) * 1.0)

    csvData.append([""]*12+[manualTotalLRE]+[""]*7+[automaticTotalLRE])

    csv_writer(csvData, os.path.join(args.landmarkRootDir, 'LREOutput.csv'))

  except Exception, e:
    print e
  sys.exit(0)


def getLandmarks(args):
  data = []
  for root, dirs, _ in os.walk(args.landmarkRootDir):
    for landmarkDir in dirs:
      files = os.listdir(os.path.join(root, landmarkDir))
      landmarkData = {
        'case': landmarkDir
      }
      for currentFile in files:
        if currentFile.endswith('-IntraopLandmarks.fcsv'):
          landmarkData['intraopLandmarks'] = os.path.join(root, landmarkDir, currentFile)
        elif currentFile.endswith('-PreopLandmarks-transformed_MANUAL.fcsv'):
          landmarkData['preopLandmarksTransformedManual'] = os.path.join(root, landmarkDir, currentFile)
        elif currentFile.endswith('-PreopLandmarks-transformed_AUTOMATIC.fcsv'):
          landmarkData['preopLandmarksTransformedAutomatic'] = os.path.join(root, landmarkDir, currentFile)
      if not 'preopLandmarksTransformedManual' in landmarkData.keys():
        print "Case data was not found for case %s" % landmarkData['case']
        continue
      data.append(landmarkData)
  return data


def calculateLRE(case):
  success, intraopLandmarks = slicer.util.loadMarkupsFiducialList(case['intraopLandmarks'], returnNode=True)
  success, preopLandmarksTransformedManual = slicer.util.loadMarkupsFiducialList(case['preopLandmarksTransformedManual'], returnNode=True)
  success, preopLandmarksTransformedAutomatic = slicer.util.loadMarkupsFiducialList(case['preopLandmarksTransformedAutomatic'], returnNode=True)

  numLandmarks = intraopLandmarks.GetNumberOfFiducials()
  caseData = {'data': [], 'manualCaseTRE': 0, 'automaticCaseTRE': 0}

  for i in range(numLandmarks):
    manualLabel = preopLandmarksTransformedManual.GetNthFiducialLabel(i)
    manualFiducialIndex = getFiducialIndexByLabel(intraopLandmarks, "-" + manualLabel.split("-")[-1])
    manualIntraopPos = ModuleLogicMixin.getTargetPosition(intraopLandmarks, manualFiducialIndex)
    manualPreopTransformedPos = ModuleLogicMixin.getTargetPosition(preopLandmarksTransformedManual, i)
    landmarkTRE = ModuleLogicMixin.get3DEuclideanDistance(manualIntraopPos, manualPreopTransformedPos)
    caseData['manualCaseTRE'] += landmarkTRE
    manual = [preopLandmarksTransformedManual.GetNthFiducialLabel(i)] +  manualPreopTransformedPos + [landmarkTRE, '', '', '']
    
    automaticLabel = preopLandmarksTransformedAutomatic.GetNthFiducialLabel(i)
    automaticFiducialIndex = getFiducialIndexByLabel(intraopLandmarks, "-" + automaticLabel.split("-")[-1])
    automaticIntraopPos = ModuleLogicMixin.getTargetPosition(intraopLandmarks, automaticFiducialIndex)
    automaticPreopTransformedPos = ModuleLogicMixin.getTargetPosition(preopLandmarksTransformedAutomatic, i)
    landmarkTRE = ModuleLogicMixin.get3DEuclideanDistance(automaticIntraopPos, automaticPreopTransformedPos)
    caseData['automaticCaseTRE'] += landmarkTRE
    automatic = [preopLandmarksTransformedAutomatic.GetNthFiducialLabel(i)] +  automaticPreopTransformedPos + [landmarkTRE, '']
    
    basic = [" ", intraopLandmarks.GetNthFiducialLabel(manualFiducialIndex)] + manualIntraopPos + ['']
    caseData['data'].append(basic+manual+automatic)

  caseData['manualCaseTRE'] /= (numLandmarks * 1.0)
  caseData['automaticCaseTRE'] /= (numLandmarks * 1.0)

  caseData['data'].append([""]*11 +[caseData['manualCaseTRE']]+[""]*7+[caseData['automaticCaseTRE']])

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