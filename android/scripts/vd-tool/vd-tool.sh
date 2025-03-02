#!/bin/bash

JAVA_CMD="java"

function print_usage {
  echo "Usage:"
  echo
  echo "  $0 [-options] -i INPUT_FILE"
  echo "    This script will convert standard SVG image to an Android Vector Drawable"
  echo ""
  echo "    -i INPUT_FILE:              the SVG File to be converted"
  echo "    -o OUTPUT:                  the output file / directory to save the converted Vector Drawable"
  echo "    -d Dimension:               specify the dimension of the output, e.g. 32 or 32x32"
  echo "    -h:                         display this message"
  echo
}

function exit_abnormal {
	print_usage
	exit 1
}

input_file=""
output=""
dimension=""

while getopts :i:o:d:hH opt; do
  case ${opt} in
    i)
      input_file=${OPTARG}
      ;;
    o)
      output=${OPTARG}
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

width=32
height=32
if [ -n "$dimension" ]; then
  if [[ "$dimension" =~ ^[0-9]+$ || "$dimension" =~ ^[0-9]+x[0-9]+$ ]]; then
    if [[ "$dimension" =~ ^([0-9]+)x([0-9]+)$ ]]; then
      width="${BASH_REMATCH[1]}"
      height="${BASH_REMATCH[2]}"
    else
      width="$dimension"
      height="$dimension"
    fi
  else
    echo "[ERROR] Invalid format for -d. Expected number or NxN format (e.g., 32 or 32x32)."
    exit 1
  fi
fi

temp_dir=$(mktemp -d)

input_fname=$(basename -- "${input_file}")
input_dir=$(dirname -- "${input_file}")
output_fname="${input_fname%.*}.xml"
output_file_tmp=${temp_dir}/${output_fname}

if [[ ! -d "${temp_dir}" ]]; then
  echo "[ERROR] Failed to create a temporary directory."
  exit 1
fi

${JAVA_CMD} -jar vector-drawable-tool.jar \
  -in "${input_file}" \
  -out "${temp_dir}" \
  -widthDp "${width}" \
  -heightDp "${height}" \
  -c \
  >/dev/null 2>&1

output_file="${input_dir}/${output_fname}"
if [ -n "$output" ]; then
    if [ -d "${output}" ]; then
        echo "${output} is a directory."
        output_file=${output}/${output_fname}
    else
        output_file=${output}
    fi
else
    echo "Output is not set. Save in the same directory as ${input_file}"
fi

cp "${output_file_tmp}" "${output_file}"

