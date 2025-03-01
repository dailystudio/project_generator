#!/bin/bash

JAVA_CMD="java"

function print_usage {
  echo "Usage:"
  echo
  echo "  $0 [-options] -i INPUT_FILE"
  echo "    This script will convert standard SVG image to an Android Vector Drawable"
  echo ""
  echo "    -i INPUT_FILE:              the SVG File to be converted"
  echo "    -o OUTPUT_FILE:             the output Vector Drawable"
  echo "    -d Dimension:               specify the dimension of the output"
  echo "    -h:                         display this message"
  echo
}

function exit_abnormal {
	print_usage
	exit 1
}

input_file=""
output_file=""
dimension=""

while getopts :i:o:d:hH opt; do
  case ${opt} in
    i)
      input_file=${OPTARG}
      ;;
    o)
      output_file=${OPTARG}
      ;;
    d)
      dimension=${OPTARG}
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

if ! command -v ${JAVA_CMD} &> /dev/null
then
    echo "[ERROR] ${JAVA_CMD} is not installed or not in PATH."
    exit 1
fi

if [ -z "${input_file}" ]; then
    echo "[ERROR] required options is missing."
    exit_abnormal
fi

${JAVA_CMD} -jar vector-drawable-tool.jar \
  -i "${input_file}" \
  -o "${output_file}" \
  -c
