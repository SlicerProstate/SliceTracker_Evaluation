import os
import sys
import argparse
import slicer
import json
import re
import csv
from datetime import datetime
from SliceTrackerUtils.sessionData import *


META_FILENAME = 'results.json'

# Slicer --python-script CollectProspectiveData.py -cr {case root} -o {output directory}


def main(argv):

  try:
    parser = argparse.ArgumentParser(description="Slicetracker Prospective Data Collection")
    parser.add_argument("-cr", "--case-root-directory", dest="caseRootDir", metavar="PATH", default="-", required=True,
                        help="Root directory that holds cases")
    parser.add_argument("-o", "--output-dir", dest="outputDir", metavar="PATH", default="-", required=True,
                        help="Output csv file directory")
    parser.add_argument("-d", "--debug", action='store_true')

    args = parser.parse_args(argv)

    if args.debug:
      slicer.app.layoutManager().selectModule("PyDevRemoteDebug")
      w = slicer.modules.PyDevRemoteDebugWidget
      w.connectButton.click()

    metafiles = []
    for root, dirs, files in os.walk(args.caseRootDir):
      metafiles += [os.path.join(root, f) for f in files if META_FILENAME in f]

    # data = {}
    """
    * How often automatic segmentation had to be modified?
    * How often initial registration had to be rerun (Cover prostate)?
    * How many times was any other than bSpline approved?
    * How many times did Kemal confirm needle confirmation images
    * Number of needle images per case
    """

    csv_writer(collect_results(metafiles), os.path.join(args.outputDir, "results.csv"))
    csv_writer(collect_general_case_information(metafiles), os.path.join(args.outputDir, "general_case_nfo.csv"))


  except Exception, e:
    print e

  sys.exit(0)


def collect_general_case_information(metafiles):
  csvData = [
    ['Case', 'Start_Time', 'Completed_Time', 'Preop_used', 'ERC', 'Segmentation_Algorithm', 'Segmentation_Started_Time',
     'Segmentation_Completed_Time', 'User_modified', 'Modification_Started_Time', 'Modification_Completed_Time']]

  for metafile in metafiles:
    caseNumber = re.search(os.path.sep + r'Case(.+?)-', metafile).group(1)
    print caseNumber
    with open(metafile) as data_file:
      data = json.load(data_file)
      events = data['procedureEvents']
      caseData = list([caseNumber, formatTime(events['caseStarted']), formatTime(events['caseCompleted']['time'])])
      caseData.append(data.has_key("preop"))
      if not data.has_key("preop"):
        caseData += ['']*4
      else:
        preop = data["preop"]
        caseData.append(preop["usedERC"])

        caseData += get_segmentation_information(preop['segmentation'])

      csvData.append(caseData)

  return csvData


def collect_results(metafiles):
  csvData = [
    ['Case', 'Series_Number', 'Series_Description', 'Series_Type', 'Time(Received)', 'Status', 'Time', 'Consent_given',
     'Registration_Type', 'Segmentation_Algorithm', 'Segmentation_Started_Time', 'Segmentation_Completed_Time',
     'User_modified', 'Modification_Started_Time', 'Modification_Completed_Time']]

  for metafile in metafiles:
    caseNumber = re.search(os.path.sep + r'Case(.+?)-', metafile).group(1)
    with open(metafile) as data_file:
      data = json.load(data_file)
      for result in data["results"]:
        caseData = [caseNumber]
        name, description = result["name"].split(": ")
        caseData.append(name)
        caseData.append(description)
        caseData.append(result['series']['type'])
        caseData.append(formatTime(result['series']['receivedTime']))
        status = result["status"]
        caseData.append(status["state"])
        caseData.append(formatTime(status["time"]))
        caseData.append(status["consentGivenBy"] if status.has_key("consentGivenBy") else None)
        caseData.append(status["registrationType"] if status.has_key("registrationType") else None)

        if result.has_key('segmentation'):
          caseData += get_segmentation_information(result['segmentation'])
        else:
          caseData += [''] * 4

        csvData.append(caseData)

  return csvData


def formatTime(t):
  return t
  try:
    return datetime.strptime(t, '%Y-%m-%dT%H:%M:%S.%fZ').strftime('%H:%M:%S')
  except ValueError:
    return t


def get_segmentation_information(root):
  data = list()
  data.append(root["algorithm"])
  data.append(formatTime(root["startTime"]))
  data.append(formatTime(root["endTime"]))

  modified = root.has_key('userModified')
  data.append(modified)
  if modified:
    data.append(formatTime(root['userModified']['startTime']))
    data.append(formatTime(root['userModified']['endTime']))
  return data


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