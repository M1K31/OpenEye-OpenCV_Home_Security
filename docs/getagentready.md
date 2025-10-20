# Agent Preparation Guide

## While Completing Tasks

***Prior to commit and push to GitHub or build and push to Docker Hub***

Please ensure all changes are documented in the change log (such as release notes). Any changes that will impact installation or uninstalling the app or image is reflected in the appropriate documentation. The readme file should be an overview with general install and use guidelines (such as quick fixes) created for a GitHub user audience. the docker_hub_overview should do the same but geared toward docker users. make an effort to consolidate and delete unneeded markdown (.md) files. Avoid creating summary documents, add changes made to the appropriate .md files. Do not commit or push archived folders or files. Avoid adding actual file paths. Always use example paths that do not resemble the paths used in development. any .MD files that reference completed tasks or features that are also mentioned in the changeling should be removed. All .md files should be saved in docs folder unless needed elsewhere. An effort to remove all image files and video files should be made to protect developer privacy. overall clean up the project after each major change.

## Check for Unexpected Errors and Plan for Future Deployment Features

When making changes to frontend elements the backend and/or database information is updated to work with any changes made. When making changes to the backed and/or database please make sure the front end UI elements operate as expected. Check all backend, frontend, and middle wear (if any) class and functions for issues with references to each other or unused code which is not needed, after each major change to the backend or front end. do the same for all APIs and routes

Ensure names used for classes, functions, and methods are consistent and do not have conflicts. File paths should not be hardcoded. Install location should be chosen by the user and all features that require the user to save or load files or folders should be requested from the user during install (unless limitations like docker deployment stop this). All install and uninstall options should be preformed by script after getting user confirmation on variables required to perform the task. all efforts should be made to shorten install times. prior to uninstall the option to save or remove image or video files if the default file paths are used. make every effort to reduce image/application size and memory usage without sacrificing desired functionality. Check for opportunities to create scripts to automate tasks for the developer.

## Check that Changes Do Not Disrupt Functionality of Other Distribution Methods

Ensure that changes made to UI or backend for docker does not disrupt or break functionality for local installations. ensure all routes are registered with the frontend UI
