import os
import sys
import argparse
import slicer
from SlicerDevelopmentToolboxUtils.mixins import ModuleLogicMixin
from SlicerDevelopmentToolboxUtils.constants import FileExtension

from SliceTrackerUtils.sessionData import *
from SliceTrackerUtils.algorithms.automaticProstateSegmentation import AutomaticSegmentationLogic
from SliceTrackerRegistration import SliceTrackerRegistrationLogic

# usage: Slicer --python-script CreateDeepLearningSegmentations.py -ld {LandmarksDirectory}

# Slicer --python-script CreateDeepLearningSegmentations.py -ld ~/Dropbox\ \(Partners\ HealthCare\)/Landmarks/

META_FILENAME = 'results.json'

CasesWithoutERC = [474,494,516,532,537,542,545,551,554,557,559,562,564]


def main(argv):

  parser = argparse.ArgumentParser(description="Slicetracker Batch DeepLearning Segmentation")
  parser.add_argument("-ld", "--landmark-root-directory", dest="landmarkRootDir", metavar="PATH", default="-",
                      required=True,
                      help="Root directory that lists all cases holding information for landmarks")
  parser.add_argument("-d", "--debug", action='store_true')

  args = parser.parse_args(argv)

  if args.debug:
    slicer.app.layoutManager().selectModule("PyDevRemoteDebug")
    w = slicer.modules.PyDevRemoteDebugWidget
    w.connectButton.click()

  for root, dirs, _ in os.walk(args.landmarkRootDir):
    for case in dirs:
      findDataAndCreateSegmentations(int(case), os.path.join(root, case))

  # import pprint
  # pprint.pprint(data)

  sys.exit(0)


def findDataAndCreateSegmentations(caseNumber, directory):

  preopVolume = os.path.join(directory, "{}-Preop.nrrd".format(caseNumber))
  preopLabel = os.path.join(directory, "{}-PreopManual-label.nrrd".format(caseNumber))
  intraopVolume = os.path.join(directory, "{}-Intraop.nrrd".format(caseNumber))
  intraopLabel = os.path.join(directory, "{}-IntraopManual-label.nrrd".format(caseNumber))
  usedERC = caseNumber not in CasesWithoutERC

  if all(os.path.exists(f) for f in [preopVolume, intraopVolume, preopLabel, intraopLabel]):
    data = {
      "caseNumber": caseNumber,
      "Preop": {
        "used_endorectal_coil": usedERC,
        "volume": preopVolume,
        "labels": {
          "Manual": preopLabel,
          "Automatic": os.path.join(directory, "{}-PreopAutomatic-label.nrrd".format(caseNumber))
        }
      },
      "Intraop": {
        "used_endorectal_coil": False,
        "volume": intraopVolume,
        "labels": {
          "Manual": intraopLabel,
          "Automatic": os.path.join(directory, "{}-IntraopAutomatic-label.nrrd".format(caseNumber))
        }
      }
    }

    createSegmentations(data, directory)
    slicer.mrmlScene.Clear(0)
    runRegistrations(data, directory)
  else:
    print "Case data was not found for case %s" % caseNumber


def createSegmentations(data, outputDir):
    caseNumber = data["caseNumber"]

    for imageType in ["Preop", "Intraop"]:

      automaticLabelPath = data[imageType]["labels"]["Automatic"]
      if not os.path.exists(automaticLabelPath):
        logic = AutomaticSegmentationLogic()
        endorectalCoilUsed = "BWH_WITHOUT_ERC" if data[imageType]["used_endorectal_coil"] is False else "BWH_WITH_ERC"
        success, volume = slicer.util.loadVolume(data[imageType]["volume"], returnNode=True)
        automaticLabel = logic.run(volume, domain=endorectalCoilUsed)
        labelName = "{}-{}Automatic-label".format(caseNumber, imageType)
        ModuleLogicMixin.saveNodeData(automaticLabel, outputDir, FileExtension.NRRD, name=labelName)
      else:
        print "Not running {} segmentation for case {} because label already exists".format(imageType, caseNumber)

      # if not preopAutomaticLabel:
      #   _, preopAutomaticLabel = slicer.util.loadVolume(preopAutomaticLabelPath, returnNode=True)


def runRegistrations(data, destination):
  caseNumber = data["caseNumber"]

  success, intraopVolume = slicer.util.loadVolume(data["Intraop"]["volume"], returnNode=True)
  intraopVolume.SetName("{}: IntraopVolume".format(caseNumber))

  for segmentationType in [ "Manual", "Automatic"]:

    success, preopVolume = slicer.util.loadVolume(data["Preop"]["volume"], returnNode=True)
    preopVolume.SetName("{}: PreopVolume".format(caseNumber))

    success, preopLabel = slicer.util.loadLabelVolume(data["Preop"]["labels"][segmentationType], returnNode=True)
    preopLabel.SetName("{}: PreopManual-label".format(caseNumber))

    success, intraopLabel = slicer.util.loadLabelVolume(data["Intraop"]["labels"][segmentationType], returnNode=True)
    intraopLabel.SetName("{}: IntraopManual-label".format(caseNumber))

    if data["Preop"]["used_endorectal_coil"] is True:
      preopVolume = applyBiasCorrection(preopVolume, preopLabel)

    result = runRegistration(intraopVolume, intraopLabel, preopVolume, preopLabel)

    if result:
      for regType, transform in result.transforms.asDict().iteritems():
        ModuleLogicMixin.saveNodeData(transform, destination, FileExtension.H5,
                                      name="{}-TRANSFORM-{}-{}".format(caseNumber, regType, segmentationType))

      for regType, volume in result.volumes.asDict().iteritems():
        if not regType in ['rigid', 'affine', 'bSpline']:
          continue
        ModuleLogicMixin.saveNodeData(volume, destination, FileExtension.NRRD,
                                      name="{}-VOLUME-{}-{}".format(caseNumber, regType, segmentationType))

def applyBiasCorrection(volume, label):
  outputVolume = slicer.vtkMRMLScalarVolumeNode()
  outputVolume.SetName('{}-N4'.format(volume.GetName()))
  slicer.mrmlScene.AddNode(outputVolume)
  params = {'inputImageName': volume.GetID(),
            'maskImageName': label.GetID(),
            'outputImageName': outputVolume.GetID(),
            'numberOfIterations': '500,400,300'}

  slicer.cli.run(slicer.modules.n4itkbiasfieldcorrection, None, params, wait_for_completion=True)
  return outputVolume

def runRegistration(fixedVolume, fixedLabel, movingVolume, movingLabel):
  registrationLogic = SliceTrackerRegistrationLogic()
  data = SessionData()
  result = data.createResult(fixedVolume.GetName())
  registrationLogic.registrationResult = result

  parameterNode = slicer.vtkMRMLScriptedModuleNode()
  parameterNode.SetAttribute('FixedImageNodeID', fixedVolume.GetID())
  parameterNode.SetAttribute('FixedLabelNodeID', fixedLabel.GetID())
  parameterNode.SetAttribute('MovingImageNodeID', movingVolume.GetID())
  parameterNode.SetAttribute('MovingLabelNodeID', movingLabel.GetID())

  registrationLogic.run(parameterNode)

  return result

if __name__ == "__main__":
  main(sys.argv[1:])

