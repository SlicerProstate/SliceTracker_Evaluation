#!/usr/bin/env bash
Slicer --python-script ApplyTransformations.py  -ld ~/Dropbox\ \(Partners\ HealthCare\)/SliceTracker_Evaluation/Landmarks/ -st Manual -tt bSpline -ft Targets
Slicer --python-script ApplyTransformations.py  -ld ~/Dropbox\ \(Partners\ HealthCare\)/SliceTracker_Evaluation/Landmarks/ -st Automatic -tt bSpline -ft Targets

Slicer --python-script ApplyTransformations.py  -ld ~/Dropbox\ \(Partners\ HealthCare\)/SliceTracker_Evaluation/Landmarks/ -st Manual -tt bSpline -ft Landmarks
Slicer --python-script ApplyTransformations.py  -ld ~/Dropbox\ \(Partners\ HealthCare\)/SliceTracker_Evaluation/Landmarks/ -st Automatic -tt bSpline -ft Landmarks

Slicer --python-script CalculateLandmarkRegistrationError.py  -ld ~/Dropbox\ \(Partners\ HealthCare\)/SliceTracker_Evaluation/Landmarks/ -o LREOutput_automatic_reg_accuracy_bSpline.csv -tt bSpline
Slicer --python-script CalculateLandmarkRegistrationError.py  -ld ~/Dropbox\ \(Partners\ HealthCare\)/SliceTracker_Evaluation/Landmarks/ -o LREOutput_absolute_reg_accuracy_bSpline.csv -tt bSpline -a

Slicer --python-script CalculateTargetingSensitivity.py -ld ~/Dropbox\ \(Partners\ HealthCare\)/SliceTracker_Evaluation/Landmarks/ -o Targeting_Sensitivity_Manual_Automatic.csv -tt bSpline
