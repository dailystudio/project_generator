#!/bin/bash

codebase_dir="com/dailystudio/codebase"
codebase_pkg="com.dailystudio.codebase"

function print_usage {
  echo "Usage:"
  echo
  echo "  $0 [-options] -n APP_NAME  -p PACKAGE_NAME"
  echo "    This script will generate a project from the templates in the codebase"
  echo ""
  echo "    -n APP_NAME:                     the application name"
  echo "    -p PACKAGE_NAME:                 the package name"
  echo "    -o OUTPUT_DIRECTORY:             the target directory of generated project"
  echo "    -h:                              display this message"
  echo
}

function exit_abnormal {
	print_usage
	exit 1
}

function renamePackage() {
  base_dir=""
  if [ "$*" != "" ] ; then
      base_dir="$*"
  fi
  anchor_dir=${PWD}

  echo "renaming packages in ${base_dir} ..."

  cd ${base_dir}
  dest_dir=""
  IFS='.' read -ra packages <<< "$pkg_name"
  for i in "${packages[@]}"; do
      dest_dir=${dest_dir}/${i}
#      echo ${dest_dir}
      mkdir -p ${i}
      cd ${i}
  done
  cd ${anchor_dir}

  echo "moving contents from ${base_dir}/${codebase_dir} to ${base_dir}/${dest_dir}/ ..."
  mv ${base_dir}/${codebase_dir}/* ${base_dir}/${dest_dir}/
  rm -rf ${base_dir}/${codebase_dir}/
}


while getopts :n:p:o:hH opt; do
  case ${opt} in
    n)
      app_name=${OPTARG}
      ;;
    p)
      pkg_name=${OPTARG}
      ;;
    o)
      outputs=${OPTARG}
      ;;
    h|H)
      print_usage
      exit 2
      ;;
    :)
      echo "[ERROR] $0: -${OPTARG} requires an argument."
      exit_abnormal
      ;;
    *)
      echo "[ERROR] $0: -${OPTARG} is unsuppported."
      exit_abnormal
      ;;
  esac
done


if [ -z "${app_name}" ] || [ -z "${pkg_name}" ]; then
    echo "[ERROR] required options is missing."
    exit_abnormal
fi

source_dir="${PWD}/codebase"
if [ ! -d "${source_dir}" ]; then
    echo "[ERROR] codebase directory does NOT exist."
    exit 1
fi

output_dir="./generated"
if [ ! -z "${outputs}" ]; then
  output_dir=${outputs}
fi

echo "----- Code Generation for Android project -----"
echo "Application name:    [${app_name}]"
echo "Package name:        [${pkg_name}]"
echo "Output directory:    [${output_dir}]"

if [ ! -d "${output_dir}" ]; then
    echo "Output directory does NOT exist, creating it ..."
    mkdir -p ${output_dir}
fi

OLD_PWD=${PWD}

echo
echo "[STEP 1]: Copying the codebase ..."
cp -af ${source_dir}/* ${output_dir}/

echo "[STEP 2]: Refactoring codes structures ..."
cd ${output_dir}
renamePackage "app/src/main/java"
renamePackage "app/src/androidTest/java"
renamePackage "app/src/test/java"

cd ${OLD_PWD}
