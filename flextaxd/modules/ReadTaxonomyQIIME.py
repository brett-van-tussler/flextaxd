#!/usr/bin/env python3 -c

'''
Read QIIME formatted taxonomy files and holds a dictionary with taxonomy tree and name translation
'''

from .ReadTaxonomy import ReadTaxonomy
from .database.DatabaseConnection import DatabaseFunctions
import logging
logger = logging.getLogger(__name__)

class ReadTaxonomyQIIME(ReadTaxonomy):
	"""docstring for ReadTaxonomyQIIME."""
	def __init__(self, taxonomy_file=False, names_dmp=False, database=False, verbose=False, taxid_base=1,**kwargs):
		super(ReadTaxonomyQIIME, self).__init__(taxonomy_file=taxonomy_file, database=database,verbose=verbose,**kwargs)
		#self.database = DatabaseFunctions(database,verbose=verbose)  # Not nessesary opens in parent class
		self.input = taxonomy_file
		self.names = {}
		self.taxid_base = taxid_base
		self.taxonomy = {}
		self.length = 0
		self.ids = 0
		self.levelDict = {
				"n": "no rank",
				"sk": "superkingdom",
				"k": "kingdom",
				"d": "domain",
				"p": "phylum",
				"c": "class",
				"o": "order",
				"f": "family",
				"g": "genus",
				"s": "species",
				"x": "strain"
		}
		self.set_qiime(True)
		### Add root name these manual nodes are required when parsing the GTDB database!
		#rootid = self.add_node("root")  ## Allways set in ReadTaxonomy
		coid = self.add_node("cellular organisms")
		bac_id = self.add_node("Bacteria")
		Euk_id = self.add_node("Eukaryota")
		arc_id = self.add_node("Archaea")
		vir_id = self.add_node("Viruses")
		oth_id = self.add_node("Other")
		unc_id = self.add_node("Unclassified")

		self.add_rank("n",qiime=True)
		self.add_rank("sk",qiime=True)
		## Add basic links
		self.add_link(child=self.root, parent=self.root,rank="n")
		self.add_link(child=coid, parent=self.root,rank="n")
		self.add_link(child=bac_id, parent=coid,rank="sk")
		self.add_link(child=Euk_id, parent=coid,rank="sk")
		self.add_link(child=arc_id, parent=coid,rank="sk")
		self.add_link(child=vir_id, parent=self.root,rank="sk")
		self.add_link(child=oth_id, parent=self.root,rank="n")
		self.add_link(child=unc_id, parent=self.root, rank="n")

	def parse_taxonomy(self):
		'''Parse taxonomy information'''
		self.qiime_to_tree()

	def parse_tree(self,tree,current_i=0):
		'''The taxonomy tree does not exist in the standard nomenclature, add a new tree'''
		### Add parent description if not exist
		level,description = self.parse_description(tree,current_i)
		if description.strip() == "":
			return False
		if level not in self.taxonomy:
			self.add_rank(level,qiime=True)
		if current_i == len(tree)-1:
			'''Top parent reached return top parent id'''
			try:
				return self.taxonomy[description]
			except KeyError:
				node_i = self.add_node(description)
			return node_i
		parent_i = self.parse_tree(tree,current_i+1)
		try:
			'''If parent is already in the database return parent ID'''
			return self.taxonomy[description]
		except KeyError:
			''' Add current node to names file '''
			node_i = self.add_node(description)

		'''When all parents exist add current relation to tree file'''
		self.add_link(node_i,parent_i,rank=level)
		'''return new tax_i'''
		return node_i

	def parse_description(self,tree,current_i):
		'''Retrieve node description from QIIME formatted tree'''
		current_level = tree[current_i]
		level, description = current_level.split("__")
		'''Fix greengenes bug with empty end nodes'''
		if description == "":
			level, description = self.parse_description(tree,current_i+1)
		return level,description


	def qiime_to_tree(self, sep="\t",reference=False):
		'''Read the qiime format file and parse out the relation tree (nodes.dmp)'''
		self.sep = sep
		self.tree = set()
		self.missed = 0
		self.errors = 0
		self.added = 0
		_ref = reference
		refDict = {"RS":"refseq","GB":"genbank"}  ## Refdict for GTDB formatted sources
		taxid_start = self.taxid_base
		with open(self.input) as f:
			'''Each row defines a genome annotation file connected to a tree level'''
			for row in f:
				if row.strip() != "":  ## If there are trailing empty lines in the file
					data = row.strip().split("\t")
					try:
						if data[0].startswith(("RS","GB")):
							'''GTDB genome annotations contain one additional annotation to their genome names eg. RS_, this function removes this'''
							reference,genome_id = data[0].split("_",1)   ## Genome ID
							genome_id = genome_id.strip()
							if not _ref:
								reference = refDict[reference]
						else:
							genome_id = data[0].strip()
							'''Greengenes adaption, empty levels'''

						#print(genome_id)
					except IndexError:
						logger.debug("Row {row} could not be parsed".format(row=data))
						self.errors +=1
					### Walk through tree and make sure all nodes back to root are annotated!
					taxonomy = list(reversed(data[-1].split(";")))
					taxonomy_i = self.parse_tree(taxonomy)
					if taxonomy_i:
						test = self.database.add_genome(genome=genome_id,_id=taxonomy_i,reference=reference)
						if not str(test).startswith("UNIQUE"):
							self.added +=1
					else:
						logger.debug("Warning taxonomy: {taxonomy} could not be parsed!!")
						self.missed +=1
		self.database.commit()
		self.length = self.taxid_base - taxid_start
		logger.info("Genomes added to database: {genomes}".format(genomes=self.added))
		logger.debug("Genomes not added to database {missed} errors {errors}".format(missed=self.missed,errors=self.errors))
		logger.info("New taxonomy ids assigned {taxidnr}".format(taxidnr=self.length))
