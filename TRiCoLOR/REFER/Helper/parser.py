#!/usr/bin/python env


#python 3 standard library

import os
import glob
import math
import subprocess


# additional modules

import pysam


## FUNCTIONS


def sub_none(list_of_coord):


	return [-999999 if v is None else v for v in list_of_coord]


def check_coverage(pysam_AlignmentFile, chromosome, start, end, coverage):

	counter = 0

	for read in pysam_AlignmentFile.fetch(chromosome, start, end):
		
		if not read.is_unmapped and not read.is_secondary and not read.is_supplementary and read.mapping_quality >= 20:

			if read.reference_start <= start and read.reference_end >= end: 

				counter +=1

	if counter >= coverage:

		return True,counter

	else:

		return False,counter


def Bamfile_Analyzer(bamfilein,chromosome,start,end, coverage, out, processor):


	bamfile=pysam.AlignmentFile(bamfilein,'rb')	

	progress,cov=check_coverage(bamfile, chromosome, start, end, coverage)

	if progress:

		with open(os.path.abspath(out+'/' + processor + '.unaligned.fa'),'w') as fastaout:

			for read in bamfile.fetch(chromosome,start,end):

				if not read.is_unmapped and not read.is_secondary and not read.is_supplementary and read.mapping_quality >= 20:

					read_start=read.reference_start
					read_end=read.reference_end

					if read_start <= start and read_end >= end:

						sequence=read.seq
						coord=sub_none(read.get_reference_positions(full_length=True))
						header=read.query_name

						s_,e_=min(coord, key=lambda x:abs(x-start)), min(coord, key=lambda x:abs(x-end)) 
						s_i,e_i = [i for i,e in enumerate(coord) if e == s_][0], [i for i,e in enumerate(coord) if e == e_][0] 

						fastaout.write('>' + header + '\n' + sequence[s_i:e_i+1] + '\n')
	
	bamfile.close()
	return cov

