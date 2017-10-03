import os
import sys
import argparse
import json
import logging
import re
import slicer
from collections import OrderedDict
from SlicerDevelopmentToolboxUtils.mixins import ModuleLogicMixin
from SlicerDevelopmentToolboxUtils.constants import FileExtension, DICOMTAGS

from SliceTrackerUtils.sessionData import *
from SliceTrackerUtils.algorithms.automaticProstateSegmentation import AutomaticSegmentationLogic
from SliceTrackerRegistration import SliceTrackerRegistrationLogic

# usage: Slicer --python-script CreateDeepLearningSegmentations.py -cr {ProstateCasesArchive} -o {OutputDirectory}

META_FILENAME = 'results.json'


def main(argv):

  # Debugging
  # slicer.app.layoutManager().selectModule("PyDevRemoteDebug")
  # w = slicer.modules.PyDevRemoteDebugWidget
  # w.connectButton.click()

  try:
    parser = argparse.ArgumentParser(description="Slicetracker Batch DeepLearning Segmentation")
    parser.add_argument("-cr", "--case-root-directory", dest="caseRootDir", metavar="PATH", default="-", required=True,
                        help="Root directory that holds cases")
    parser.add_argument("-o", "--output-root-directory", dest = "outputRootDir", metavar = "PATH", default = "-", required = True,
                        help="Root directory of output holding sub directories named with case numbers")
    args = parser.parse_args(argv)

    metafiles = []
    for root, dirs, files in os.walk(args.caseRootDir):
      metafiles = metafiles + [os.path.join(root, f) for f in files if META_FILENAME in f]


    data = {}

    # find case number
    # #TODO: handle Case 486
    for metafile in metafiles:
      caseNumber = re.search('/Case(.+?)-', metafile).group(1)
      if not os.path.exists(metafile):
        raise ValueError("Meta file %s does not exist" % metafile)
      data[caseNumber] = getVolumesAndLabels(metafile)

    # import pprint
    # pprint.pprint(data)

    applySegmentations(data, args.outputRootDir)

  except Exception, e:
    print e
  sys.exit(0)


def getVolumesAndLabels(metafile):

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
          "preop": {
            "volume" : os.path.join(path, jsonResult["movingVolume"]),
            "used_endorectal_coil": data["VOLUME-PREOP-N4"] is not None,
            "labels": {
              "manual": os.path.join(path, jsonResult["movingLabel"]),
              "automatic": ""
            }
          },
          "intraop": {
            "volume": os.path.join(path, jsonResult["fixedVolume"]),
            "labels": {
              "manual": os.path.join(path, jsonResult["fixedLabel"]),
              "automatic": ""
            }
          }
        }

  return None


def applySegmentations(cases, outputDir):
  numEndoRectalCoil = numNoEndoRectalCoil = 0

  for caseNumber, data in cases.iteritems():
    if data is None:
      logging.error("Data could not be retrieved for case %s. Please check the meta information for that case" % caseNumber)
      continue

    if "N4" in data["preop"]["volume"]:
      endorectalCoilUsed = "BWH_WITH_ERC"
      numEndoRectalCoil += 1
    else:
      endorectalCoilUsed = "BWH_WITHOUT_ERC"
      numNoEndoRectalCoil += 1

    slicer.mrmlScene.Clear(0)
    destination = os.path.join(outputDir, caseNumber)
    if not os.path.exists(destination):
      ModuleLogicMixin.createDirectory(destination)

    success, preopVolume = slicer.util.loadVolume(data["preop"]["volume"], returnNode=True)
    preopVolume.SetName("{}: PreopVolume".format(caseNumber))

    success, preopManualLabel = slicer.util.loadLabelVolume(data["preop"]["labels"]["manual"], returnNode=True)
    preopManualLabel.SetName("{}: PreopLabel_Manual".format(caseNumber))

    success, intraopVolume = slicer.util.loadVolume(data["intraop"]["volume"], returnNode=True)
    intraopVolume.SetName("{}: IntraopVolume".format(caseNumber))

    success, intraopManualLabel = slicer.util.loadLabelVolume(data["intraop"]["labels"]["manual"], returnNode=True)
    intraopManualLabel.SetName("{}: IntraopLabel_Manual".format(caseNumber))

    ModuleLogicMixin.saveNodeData(preopVolume, destination, FileExtension.NRRD, overwrite=False)
    ModuleLogicMixin.saveNodeData(preopManualLabel, destination, FileExtension.NRRD, overwrite=False)
    ModuleLogicMixin.saveNodeData(intraopVolume, destination, FileExtension.NRRD, overwrite=False)
    ModuleLogicMixin.saveNodeData(intraopManualLabel, destination, FileExtension.NRRD, overwrite=False)

    preopAutomaticLabel = None
    preopAutomaticLabelName = "{}-PreopLabel_Automatic".format(caseNumber)
    preopAutomaticLabelPath = os.path.join(destination, preopAutomaticLabelName+FileExtension.NRRD)
    if not os.path.exists(preopAutomaticLabelPath):
      logic = AutomaticSegmentationLogic()

      # print "Case %s used endorectal coil: %s == %s?" % (caseNumber, endorectalCoilUsed, data["preop"]["used_endorectal_coil"])
      preopAutomaticLabel = logic.run(preopVolume, domain=endorectalCoilUsed)
      ModuleLogicMixin.saveNodeData(preopAutomaticLabel, destination, FileExtension.NRRD, name=preopAutomaticLabelName)
    else:
      print "Not running preop segmentation for case %s because label already exists" % caseNumber

    if not preopAutomaticLabel:
      _, preopAutomaticLabel = slicer.util.loadVolume(preopAutomaticLabelPath, returnNode=True)

    intraopAutomaticLabel = None
    intraopAutomaticLabelName = "{}-IntraopLabel_Automatic".format(caseNumber)
    intraopAutomaticLabelPath = os.path.join(destination, intraopAutomaticLabelName+FileExtension.NRRD)
    if not os.path.exists(intraopAutomaticLabelPath):
      logic = AutomaticSegmentationLogic()
      intraopAutomaticLabel = logic.run(intraopVolume, domain="BWH_WITHOUT_ERC")
      ModuleLogicMixin.saveNodeData(intraopAutomaticLabel, destination, FileExtension.NRRD,
                                    name=intraopAutomaticLabelName)
    else:
      print "Not running intraop segmentation for case %s because label already exists" % caseNumber

    if not intraopAutomaticLabel:
      _, intraopAutomaticLabel = slicer.util.loadVolume(intraopAutomaticLabelPath, returnNode=True)


    result = runRegistration(intraopVolume, intraopAutomaticLabel, preopVolume, preopAutomaticLabel)

    if result:
      for regType, transform in result.transforms.asDict().iteritems():
        ModuleLogicMixin.saveNodeData(transform, destination, FileExtension.H5,
                                      name="{}-TRANSFORM-{}".format(caseNumber, regType))

      for regType, volume in result.volumes.asDict().iteritems():
        if not regType in ['rigid', 'affine', 'bSpline']:
          continue
        ModuleLogicMixin.saveNodeData(volume, destination, FileExtension.NRRD,
                                      name="{}-VOLUME-{}".format(caseNumber, regType))

  print "Number of cases WITH endorectal coil: %s" % numEndoRectalCoil
  print "Number of cases WITHOUT endorectal coil: %s" % numNoEndoRectalCoil

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

