import sys
import os
import json
import re
import argparse
import logging
import slicer
from collections import OrderedDict
import shutil
import numpy as np
import SimpleITK as sitk

from SliceTrackerUtils.sessionData import *
from SlicerDevelopmentToolboxUtils.mixins import ModuleLogicMixin
from SlicerDevelopmentToolboxUtils.constants import FileExtension
import DeepInfer

# usage: Slicer --python-script CopyNeedleImagesAndData.py -cr {ProstateCasesArchive} -od {outputCaseDirectory}

# Slicer --python-script CopyNeedleImagesAndData.py  -cr "/Users/christian/Dropbox (Partners HealthCare)/SliceTracker_Evaluation/Prospective/ClinicalCases" -od "/Users/christian/Dropbox (Partners HealthCare)/SliceTracker_Evaluation/Prospective/TRE"

META_FILENAME = 'results.json'


def main(argv):

  # try:
  parser = argparse.ArgumentParser(description="Slicetracker Batch Copy Needle image data")
  parser.add_argument("-cr", "--case-root-directory", dest="caseRootDir", metavar="PATH", default="-", required=True,
                      help="Root directory that holds cases")
  parser.add_argument("-od", "--output-landmarks-directory", dest = "outputCaseDirectory", metavar = "PATH", default = "-",
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

  import pprint
  pprint.pprint(data)

  copyData(data, args.outputCaseDirectory)
  sys.exit(0)


def getData(metafile):
  needle_data = []

  with open(metafile) as data_file:
    data = json.load(data_file)
    logging.debug("Reading metafile %s" % metafile)
    path = os.path.dirname(metafile)

    for result in data["results"]:
      if result["status"]["state"] == RegistrationStatus.APPROVED_STATUS and result["series"]["type"] == "GUIDANCE":
        needle_data.append({
          "seriesNumber": RegistrationResult.getSeriesNumberFromString(result["name"]),
          "path": path,
          "label": result["labels"]["fixed"],
          "volume": result["volumes"]["fixed"],
          "targets": result["targets"]["approved"]["fileName"] # TODO: what about user modified?
        })
  return needle_data


def copyData(data, outputDir):

  logic = DeepInfer.DeepInferLogic()
  parameters = DeepInfer.ModelParameters()
  segmenter_json_file = os.path.join(DeepInfer.JSON_LOCAL_DIR, "ProstateNeedleFinder.json")
  with open(segmenter_json_file, "r") as fp:
    j = json.load(fp, object_pairs_hook=OrderedDict)

  iodict = parameters.create_iodict(j)
  dockerName, modelName, dataPath = parameters.create_model_info(j)

  for case, caseData in data.iteritems():
    if not caseData:
      continue
    outputCaseDir = os.path.join(outputDir, case)
    if not os.path.exists(outputCaseDir):
      ModuleLogicMixin.createDirectory(outputCaseDir)

    print "processing data of case %s" %case

    for data in caseData:
      seriesNumber = data["seriesNumber"]

      inputs = dict()

      temp = os.path.join(outputCaseDir, "{}-label.nrrd".format(seriesNumber))
      if not os.path.exists(temp):
        copy(os.path.join(data["path"], data["label"]), temp)
      # success, inputs['InputProstateMask'] = slicer.util.loadLabelVolume(temp, returnNode=True)

      temp = os.path.join(outputCaseDir, "{}-volume.nrrd".format(seriesNumber))
      if not os.path.exists(temp):
        copy(os.path.join(data["path"], data["volume"]), temp)
      # success, inputs['InputVolume'] = slicer.util.loadVolume(temp, returnNode=True)

      temp = os.path.join(outputCaseDir, "{}-targets.fcsv".format(seriesNumber))
      if not os.path.exists(temp):
        copy(os.path.join(data["path"], data["targets"]), temp)


      temp = os.path.join(outputCaseDir, "{}-needle-label.nrrd".format(seriesNumber))
      if not os.path.exists(temp):
        outputs = dict()
        outputs['OutputLabel'] = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")
        outputs['OutputFiducialList'] = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode")

        params = dict()
        params['InferenceType'] = 'Ensemble'

        logic.executeDocker(dockerName, modelName, dataPath, iodict, inputs, params)
        logic.updateOutput(iodict, outputs)

        ModuleLogicMixin.saveNodeData(outputs['OutputLabel'], outputCaseDir, FileExtension.NRRD,
                                      name="{}-needle-label".format(seriesNumber))
        ModuleLogicMixin.saveNodeData(outputs['OutputFiducialList'], outputCaseDir, FileExtension.FCSV,
                                      name="{}-needle-tip".format(seriesNumber))

      temp = os.path.join(outputCaseDir, "{}-needle-centerline.fcsv".format(seriesNumber))
      if not os.path.exists(temp):
        centerLine = CenterLineCalculator(os.path.join(outputCaseDir, "{}-needle-label.nrrd".format(seriesNumber)))
        points_ijk = centerLine.get_needle_points_ijk()
        points_ras = centerLine.convert_points_ijk_to_ras(points_ijk)
        centerlineNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode")
        for point in points_ras:
          centerlineNode.AddFiducialFromArray(point)
        centerlineNode.SetLocked(True)
        ModuleLogicMixin.saveNodeData(centerlineNode, outputCaseDir, FileExtension.FCSV,
                                      name="{}-needle-centerline".format(seriesNumber))


def copy(source, destination):
  print "Copying from %s to %s" % (source, destination)
  shutil.copy(source, destination)


class CenterLineCalculator:

  def __init__(self, path):
    self.label = sitk.ReadImage(path)
    self.nda = sitk.GetArrayFromImage(self.label)

  def bounding_box(self, arr, padding=0, square=False):
    a = np.where(arr != 0)
    if a[0].size and a[1].size:
      min_ax0 = np.min(a[0])
      max_ax0 = np.max(a[0])
      min_ax1 = np.min(a[1])
      max_ax1 = np.max(a[1])
      if square:
        min_ax = min(min_ax0, min_ax1)
        max_ax = max(max_ax0, max_ax1)
        return min_ax - padding, max_ax + padding, min_ax - padding, max_ax + padding
      return min_ax0 - padding, max_ax0 + padding, min_ax1 - padding, max_ax1 + padding

  def get_needle_points_ijk(self):
    needle_slices = np.nonzero(np.sum(np.sum(self.nda, axis=1), axis=1))[0]
    n_points = len(needle_slices)
    points_array = np.zeros((n_points, 3), dtype=np.int)
    for index, slice_no in enumerate(needle_slices):
      slice_nda = self.nda[slice_no]
      y1, y2, x1, x2 = self.bounding_box(slice_nda)
      points_array[index, 0] = x1 + int((x2 - x1) / 2)
      points_array[index, 1] = y1 + int((y2 - y1) / 2)
      points_array[index, 2] = slice_no
    return points_array

  def convert_points_ijk_to_ras(self, points):
    reconstructed_needle_tube_nda = np.zeros_like(self.nda)
    points_ras = np.zeros((len(points), 3))
    for index, point in enumerate(points):
      points_ras[index] = np.asarray(self.label.TransformIndexToPhysicalPoint(point))
    # lps to ras conversion
    points_ras[:, 0] *= -1
    points_ras[:, 1] *= -1
    return points_ras


if __name__ == "__main__":
  main(sys.argv[1:])