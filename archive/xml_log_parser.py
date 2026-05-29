#!/usr/bin/python3
import pandas as pd
import xmltodict
import numpy

File="Journal.2025-06-09T181639.01.log"

with open(File) as f:
    lines = [line.rstrip() for line in f]
    x=pd.read_xml(lines)
    print(x)
