import os
import sys
import argparse
import slicer
import pandas
import csv

from LabelStatistics import LabelStatisticsLogic
from SliceTrackerUtils.sessionData import *


# usage: Slicer --no-main-window --python-script CalculateProstateVolumes.py -sd ~/Dropbox\ \(Partners\ HealthCare\)/SliceTracker_Evaluation/Segmentations/ -o Volumes.csv


def main(argv):

  try:
    parser = argparse.ArgumentParser(description="Slicetracker Transform Applicator")
    parser.add_argument("-sd", "--segmentations-root-directory", dest="segmentationsDir", metavar="PATH", default="-",
                        required=True, help="Root directory listing cases holding information manual and automatic label")
    parser.add_argument("-o", "--output-csv-file", dest="outputFile", metavar="PATH", default="-",
                        required=True, help="Output csv file to write information to")
    args = parser.parse_args(argv)

    data = processSegmentationsDirectory(args.segmentationsDir)
    calculateVolumes(data)
    writeData(os.path.join(args.segmentationsDir, args.outputFile), data)

    # import pprint
    # pprint.pprint(data)
    # write to csv

  except Exception, e:
    print e
  sys.exit(0)


def processSegmentationsDirectory(directory):
  # directory lists sub directory named with their case number

  data = {}

  for root, dirs, _ in os.walk(directory):
    for caseDir in dirs:
      data[caseDir] = getData(os.path.join(root, caseDir))
  return data


def getData(directory):

  data = {
    "preop": {
      "manual": dict(),
      "automatic": dict()
    },
    "intraop": {
      "manual": dict(),
      "automatic": dict()
    }
  }

  def absPath(fileName):
    return os.path.join(directory, fileName)

  for currentFile in os.listdir(directory):
    if currentFile.find("Volume.nrrd") != -1:
      data["preop" if currentFile.find("Preop") != -1 else "intraop"]["volume"] = absPath(currentFile)
    elif currentFile.find("IntraopLabel") != -1:
      data["intraop"]["manual" if "Manual" in currentFile else "automatic"]["label"] = absPath(currentFile)
    elif currentFile.find("PreopLabel") != -1:
      data["preop"]["manual" if "Manual" in currentFile else "automatic"]["label"] = absPath(currentFile)
  return data


def calculateVolumes(data):

  for case, caseData  in data.iteritems():
    for stage, stageData in caseData.iteritems():
      success, volume = slicer.util.loadVolume(stageData["volume"], returnNode=True)
      for segmentationType, segData in stageData.iteritems():
        if not type(segData) is str:
          success, label = slicer.util.loadLabelVolume(segData["label"], returnNode=True)
          logic = LabelStatisticsLogic(volume, label)
          segData["statistics"] = dict()
          for k in ["Volume mm^3", "Volume cc"]:
            segData["statistics"][k] = logic.labelStats[logic.labelStats["Labels"][-1], k]
            #             data[case][stage][segmentationType][k] = logic.labelStats[logic.labelStats["Labels"][-1], k]


def writeData(outputFile, data):


  csvData = [['Case', 'Manual Preop', '', 'Automatic Preop', '', 'Manual Intraop', '', 'Automatic Intraop', ''],
             ['', "Volume mm^3", "Volume cc", "Volume mm^3", "Volume cc", "Volume mm^3", "Volume cc", "Volume mm^3", "Volume cc"]]


  for case, caseData in data.iteritems():
    currentData = [case]
    for stage in ["preop", "intraop"]:
      stageData = caseData[stage]
      for segType in ["manual", "automatic"]:
        for stat in ["Volume mm^3", "Volume cc"]:
          currentData.append(stageData[segType]["statistics"][stat])
    csvData.append(currentData)

  with open(outputFile, "wb") as csv_file:
    writer = csv.writer(csv_file, delimiter=',')
    for line in csvData:
      writer.writerow(line)

if __name__ == "__main__":
  main(sys.argv[1:])

