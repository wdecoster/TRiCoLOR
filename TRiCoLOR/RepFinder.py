#!/usr/bin/python env

import re
import itertools
import bisect
import sys
import pyfaidx
import pysam
from collections import defaultdict
from operator import itemgetter


def GetLargestFromNested(intervals): 

	i=0

	purified=[]

	while i < len(intervals):


		if i==0:

			if intervals[i][2] > intervals[i+1][1]: #the two intervals overlap

				if intervals[i+1][3]*len(intervals[i+1][0]) > intervals[i][3]*len(intervals[i][0]):

					purified.append(intervals[i+1])
					i+=2

				else: 

					purified.append(intervals[i])
					i+=2

			else:

				purified.append(intervals[i])
				purified.append(intervals[i+1])
				i+=2

		else:

			if intervals[i][1] < purified[-1][2]:

				if intervals[i][3]*len(intervals[i][0]) > purified[-1][3]*len(purified[-1][0]):

					purified.remove(purified[-1])
					purified.append(intervals[i])
					i+=1

				else:

					#don't remove the existing interval
					i+=1

			else:

				purified.append(intervals[i])
				i+=1


	return list(purified)



def RepeatsFinder(string,kmer,times): #find repetitions in string using the RegEx approach. Times is the lower bound for the number of times a repetition must occur

	if kmer != 0 and times == 0:

		my_regex = r'(.{'  + str(kmer) + r'})\1+'

	elif kmer != 0 and times != 0:

		my_regex = r'(.{'  + str(kmer) + r'})\1{' + str(times-1) + r',}'

	elif kmer == 0 and times != 0:

		my_regex = r'(.+?)\1{' + str(times-1) + r',}'

	else:

		my_regex = r'(.+?)\1+'

	r=re.compile(my_regex)

	for match in r.finditer(string):

		yield (match.group(1), match.start(1), match.start(1)+len(match.group(1))*int(len(match.group(0))/len(match.group(1)))-1,int(len(match.group(0))/len(match.group(1))))


def Get_Alignment_Positions(bamfilein): #as the consensus sequence is supposed to generate just one sequence aligned to the reference, secondary alignments are removed
	
	coords=[]
	seq=[]

	bamfile=pysam.AlignmentFile(bamfilein,'rb')

	for read in bamfile.fetch():

		if not read.is_unmapped and not read.is_secondary: 

			coords = read.get_reference_positions(full_length=True)
			seq=read.seq

		else:

			bamfile.close()
			return coords,seq

	bamfile.close()

	return coords,seq


def modifier(coordinates): #fast way to remove None and substitute with closest number in list

	
	coordinates=[el+1 if el is not None else el for el in coordinates] #get true coordinates
	start = next(ele for ele in coordinates if ele is not None)

	for ind, ele in enumerate(coordinates):
		
		if ele is None:

			coordinates[ind] = start
		
		else:

			start = ele

	return coordinates


def Get_Alignment_Coordinates(coord_list,repetitions): 

	rep_coord_list=[(a,b,c,d) for a,b,c,d in zip([repetition[0] for repetition in repetitions],[coord_list[repetition[1]] for repetition in repetitions],[coord_list[repetition[2]] for repetition in repetitions],[repetition[3] for repetition in repetitions])]

	return rep_coord_list


def look_for_self(rep,sequence): #build another regular expression, looking for the core of the repetition

	for match in re.finditer(rep,sequence):

		yield (match.group(), match.start(), match.start()+len(match.group())*int(len(match.group())/len(match.group()))-1,int(len(match.group())/len(match.group())))


def dfs(adj_list, visited, vertex, result, key):

	visited.add(vertex)
	result[key].append(vertex)

	for neighbor in adj_list[vertex]:

		if neighbor not in visited:

			dfs(adj_list, visited, neighbor, result, key)


def neighbors(pattern, d): # works even with very long patterns

	assert(d <= len(pattern))

	chars='ATCG'

	if d == 0:

		return [pattern]

	r2 = neighbors(pattern[1:], d-1)
	r = [c + r3 for r3 in r2 for c in chars if c != pattern[0]]

	if (d < len(pattern)):

		r2 = neighbors(pattern[1:], d)
		r += [pattern[0] + r3 for r3 in r2]

	return r


def d_neighbors(pattern,d=1):

	return sum([neighbors(pattern, d2) for d2 in range(d + 1)], [])


def one_deletion_neighbors(word):

	splits = [(word[:i], word[i:]) for i in range(len(word) + 1)]
	deletes = [left + right[1:] for left,right in splits if right]

	return deletes


def check_ref(ref_seq, test_seq): #pyfaidx way to get start/end in fasta is valid, as coordinates are adjusted one-based

	return ref_seq != test_seq


def get_rep_num(reps,interval,sequence): #get the most-likely corrected number of repetition based on the assumptions commented in corrector function

	
	test_case=[]

	test_case.extend(d_neighbors(reps))
	test_case.extend(one_deletion_neighbors(reps))
	substr=sequence[interval[0]:interval[-1]+len(reps)]
	self_=list(look_for_self(reps,substr))
	where_in_sub=[el[1] for el in self_]

	i=0 # position in string
	l=0 # position in occurences list
	count=0 #number of putative repetitions

	while i <= where_in_sub[-1]:

		if i in where_in_sub: #is a perfect repetition

			i+= len(reps)
			count+=1
			l+=1

		else:

			dim=where_in_sub[l]-i

			if substr[i:i+dim] in test_case:

				i+= dim
				count+=1 #what we see is a deletion of an existing repetition, so we will count this as a repetition
			
			else:

				i+= dim
				count+=0 #don't consider this a repetition


	return count




def corrector(ref_seq, sequence, repetitions, coordinates, size, allowed=1): # correct for one-nucleotide insertions, substitutions and deletions between a repetition already started if this alterations are not in the reference sequence

	corrected=[]

	coords=modifier(coordinates)

	for reps in list(set(el[0] for el in repetitions)):

		self_=list(look_for_self(reps,sequence))
		self__= Get_Alignment_Coordinates(coords,self_)
		self_=[el[1] for el in self_]

		ranges=[]

		for i in range(len(self_)-1):

			if self__[i+1][1]-self__[i][1] <= len(reps): #allows repetitions that have same coordinates 'cause are 'insertions'

				if self_[i+1] - self_[i] == len(reps) or self_[i+1] - self_[i] == len(reps) + allowed:

					ranges.append((self_[i],self_[i+1]))

			elif self__[i+1][1]-self__[i][1] == len(reps)+allowed and sequence[self_[i+1]-(len(reps)-1):self_[i+1]] not in one_deletion_neighbors(reps) and check_ref(ref_seq[self__[i][1]-1: self__[i+1][1]],sequence[self_[i]: self_[i+1]+1]): #allows a mono-nucleotide insertion that broke the previous RegEx; for dinucleotide repetitions, can't discriminate between mono-nucleotide insertion or deletion if they are edit distance 1 neighbors and in that case are considered deletions
				
				ranges.append((self_[i],self_[i+1]))

			elif self__[i+1][1]-self__[i][1] == len(reps)+(len(reps)-1)+allowed and sequence[self_[i+1]-len(reps):self_[i+1]] in d_neighbors(reps) and check_ref(ref_seq[self__[i][1]-1: self__[i+1][1]],sequence[self_[i]: self_[i+1]+1]): #allows a mono-nucleotide substitution that broke the previous RegEx

				ranges.append((self_[i],self_[i+1]))

			elif self__[i+1][1]-self__[i][1] == len(reps)+(len(reps)-2)+allowed and sequence[self_[i+1]-(len(reps)-1):self_[i+1]] in one_deletion_neighbors(reps) and check_ref(ref_seq[self__[i][1]-1: self__[i+1][1]],sequence[self_[i]: self_[i+1]+1]): #allows a mono-nucleotide deletion that broke the previous RegEx

				ranges.append((self_[i],self_[i+1]))

		collapsed_ranges= defaultdict(list)
		
		for x, y in ranges:

			collapsed_ranges[x].append(y)
			collapsed_ranges[y].append(x)

		result = defaultdict(list)
		visited = set()
		
		for vertex in collapsed_ranges:

			if vertex not in visited:

				dfs(collapsed_ranges, visited, vertex, result, vertex)

		if len(result) != 0:

			new_reps=Get_Alignment_Coordinates(coords,[(reps, i[0], i[-1]+(len(reps)-1), get_rep_num(reps,i,sequence)) for i in result.values()])

			corrected.extend(new_reps)

		else:

			continue
	
	#sort repetitions using each start

	s_c_=sorted(corrected, key=itemgetter(1,2))

	#filter out overlapping repetitions, considering only larger ones

	purified=sorted(GetLargestFromNested(s_c_), key=itemgetter(1,2))
	
	significant=[]
	
	for (a,b,c,d) in s_c_: #discard reps that falls entirely in soft-clipped intervals, as we cannot be sure of their number
		
		if (a,b,c,d) in purified and len(a)*d >= size:

			if b == coords[0] and c == coords[0] and coordinates[0] is None: #exclude intervals that fall entirely in left soft-clipped regions, as coordinates-correction method may fail

				continue

			elif b == coords[-1] and c == coords[-1] and coordinates[-1] is None: #exclude intervals that fall entirely in right soft-clipped regions as coordinates-correction method may fail
				
				continue
				
			else:

				significant.append((a,b,c,d))
				
		else:

			continue
			
		
	return significant
	
	
	
