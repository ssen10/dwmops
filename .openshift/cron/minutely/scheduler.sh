#!/bin/bash
CHECK=$0
minute=$(date +%M)
x=$((10#$minute % 30 ))

# Run clean queues script

echo "running cleanqueues.sh"
bash $OPENSHIFT_REPO_DIR/runscripts/minute_cleanqueues.sh

# create conditional vars

DAILY_REFRESH=$(ps ax | sed -n /Eloqua_Contacts.Indicators_Refresh.py/p | grep -v sed | grep -v "${CHECK}")
DWM_GET=$(ps ax | sed -n /Eloqua_Contacts_GetDWM.py/p | grep -v sed | grep -v "${CHECK}")
DWM_POST=$(ps ax | sed -n /Eloqua_Contacts_PostDWM.py/p | grep -v sed | grep -v "${CHECK}")
DWM_INDICATORS=$(ps ax | sed -n /Eloqua_Contacts_UpdateContactsIndicators.py/p | grep -v sed | grep -v "${CHECK}")
DWM_RUN=$(ps ax | sed -n /Eloqua_Contacts_RunDWM.py/p | grep -v sed | grep -v "${CHECK}")

# Begin conditionals

# If daily refresh script is not running then proceed, else EXIT

if [ "${#DAILY_REFRESH}" -eq 0 ]; then
  # If is beginning of half hour, run GetDWM
  if [ $x -eq 0 ]; then
    echo "running getdwm.sh"
    bash $OPENSHIFT_REPO_DIR/runscripts/halfhour_getdwm.sh
  elif [ $x -eq 15 ]; then
    # If is middle of half hour (XX:15, XX:45), run POSTDWM
    echo "running postdwm.sh"
    bash $OPENSHIFT_REPO_DIR/runscripts/halfhour_postdwm.sh
  else
    # Else check conditionals to run other scripts
    if [ "${#DWM_GET}" -eq 0 ] && [ "${#DWM_POST}" -eq 0 ]; then
      ## if GET or POST not running then proceed, else exit
      if [ "${#DWM_RUN}" -eq 0 ]; then
        echo "running rundwm.sh"
        bash $OPENSHIFT_REPO_DIR/runscripts/minute_rundwm.sh
      else
        echo "DWM Run script still running..."
      fi
      if [ "${#DWM_INDICATORS}" -eq 0 ]; then
        # If dwm indicator refresh not running then proceed, else exit
        echo "running rundwmindicators.sh"
        bash $OPENSHIFT_REPO_DIR/runscripts/minute_rundwmindicators.sh
      else
        echo "DWM Indicator Refresh still running..."
      fi
    else
      echo "GET or POST still running..."
    fi
  fi
else
  echo "daily refresh scripts still running..."
fi
