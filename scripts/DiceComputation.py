import os
import sys
import argparse
import slicer
import logging
import csv
from SlicerDevelopmentToolboxUtils.mixins import ModuleLogicMixin
from SliceTrackerUtils.sessionData import *
import SimpleITK as sitk
import sitkUtils


# usage: Slicer.exe --no-main-window --python-script DiceComputation.py -ld {LandmarksDirectory}


validForRegistrationAccuracy = [278,281,285,295,303,304,306,310,331,333,348,357,358,363,366,370,393,395,398,410,415,416,
                                417,423,426,437,438,442,444,445,458,461,463,467,469,471,473,474,483,486,494,510,513,514,
                                515,516,519,522,524,530,532,534,537,540,542,545,547,548,551,554,557,559,560,561,562,564,
                                567,570,572,573,576,579,580]

def main(argv):

  try:
    parser = argparse.ArgumentParser(description="Slicetracker Transform Applicator")
    parser.add_argument("-ld", "--landmark-root-directory", dest="landmarkRootDir", metavar="PATH", default="-", required=True,
                        help="Root directory that lists all cases holding information for landmarks")
    parser.add_argument("-o", "--output-file", dest="outputFile", metavar="PATH", default="-", required=True,
                        help="Output csv file")
    parser.add_argument("-d", "--debug", action='store_true')
    args = parser.parse_args(argv)

    if args.debug:
      slicer.app.layoutManager().selectModule("PyDevRemoteDebug")
      w = slicer.modules.PyDevRemoteDebugWidget
      w.connectButton.click()

    csvData = [['Case','Preop', 'Intraop']]

    csvData += computeDice(args)

    csv_writer(csvData, os.path.join(args.landmarkRootDir, args.outputFile))

  except Exception, e:
    print e
  sys.exit(0)


def computeDice(args):
  data = []
  for root, dirs, _ in os.walk(args.landmarkRootDir):
    for case in dirs:
      caseData =[case]
      for imageType in ["Preop", "Intraop"]:
        logging.info("Processing case %s" %case)
        if int(case) not in validForRegistrationAccuracy:
          logging.info("Skipping case %s that is not in list of valid cases" % case)
          continue

        manualLabel = os.path.join(root, case, "{}-{}Manual-label.nrrd".format(case, imageType))
        automaticLabel = os.path.join(root, case, "{}-{}Automatic-label.nrrd".format(case, imageType))

        if all(os.path.exists(f) for f in [manualLabel, automaticLabel]):

          success, manualLabelNode = slicer.util.loadLabelVolume(manualLabel, returnNode=True)
          success, automaticLabelNode = slicer.util.loadLabelVolume(automaticLabel, returnNode=True)
          caseData.append(getDice(manualLabelNode, automaticLabelNode))
        else:
          print "Data was not found for case %s" % case
      data.append(caseData)
  return data


def runBRAINSResample(inputVolume, referenceVolume):
  params = {'inputVolume': inputVolume, 'referenceVolume': referenceVolume, 'outputVolume': inputVolume,
            'interpolationMode': 'NearestNeighbor', 'pixelType':'uchar'}

  logging.debug('About to run BRAINSResample CLI with those params: %s' % params)
  slicer.cli.run(slicer.modules.brainsresample, None, params, wait_for_completion=True)
  return inputVolume

def getDice(reference, moving):
  moving = runBRAINSResample(moving, reference)

  referenceAddress = sitkUtils.GetSlicerITKReadWriteAddress(reference.GetName())
  image_reference = sitk.ReadImage(referenceAddress)

  movingAddress = sitkUtils.GetSlicerITKReadWriteAddress(moving.GetName())
  image_input = sitk.ReadImage(movingAddress)

  # make sure both labels have the same value
  threshold = sitk.BinaryThresholdImageFilter()
  threshold.SetUpperThreshold(100)
  threshold.SetLowerThreshold(1)
  threshold.SetInsideValue(1)
  image_reference = threshold.Execute(image_reference)
  image_input = threshold.Execute(image_input)

  measureFilter = sitk.LabelOverlapMeasuresImageFilter()
  if measureFilter.Execute(image_reference, image_input):
    print 'filter executed'
  value = measureFilter.GetDiceCoefficient()

  return value


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