#!/bin/bash
OUT=out
ZIPNAME=results.zip
if [ -d "$OUT" ]; then
  zip -r $ZIPNAME $OUT
  echo "Created $ZIPNAME"
else
  echo "Directory $OUT not found"
fi
