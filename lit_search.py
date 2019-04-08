import pandas as pd
import os
import yaml
import requests
from functools import reduce
from operator import getitem
import atoma
from collections import namedtuple
from xml.etree import ElementTree as ET

standard_dic=namedtuple('standard_dic',['start','query','api_key','num_per_page'],defaults=(0,None,None,None))





class LitSearch():
	URL=None
	result_key=None
	numbers=True
	pages=False
	
	df_cols=['title','type','abstract','authors','date','journal',
		'page','volume','publisher','doi','url','api_source']
	
	@staticmethod
	def getitem_from_dict(dataDict, mapList):
		"""Iterate nested dictionary"""
		#this works for nested dictionaries, lists and tuples
		return reduce(getitem, mapList, dataDict)
	
	


	def __init__(self,key_path='lit_review_api.yml',query_setup_path='lit_search_query_setup.yml'):
		self.set_key_path(key_path)
		self.set_keys()
		self.set_key()
		self.load_par_dic(path=query_setup_path,setv=True)
		
	def standard_dic(self,query):
		try:
			api_key=self.key
		except AttributeError:
			api_key=None
		
		return standard_dic(**{'api_key':api_key,'query':query})
		
	def set_key_path(self,key_path):
		self.key_path=key_path
		
	def set_keys(self):
		self.key_dic=self.yamlLoad(self.key_path)
		
	def set_key(self):
		try:
			self.key=self.key_dic[self.key_name]
		except KeyError:
			self.key=None
			print(f'Warning, no api key set in {self.key_path}')


	def set_search_terms(self):
		cwd=os.getcwd()
		path=os.path.join(cwd,'Lit Review Tables','lit review tables.xlsx')
		df=pd.read_excel(path,header=[0,1,2],index_col=0)
		srch_dic={}
		for srch in df.columns.levels[0]:
			srch_dic[srch]=df.loc[:,(srch)]
			
		self.search_terms=srch_dic
		return srch_dic
		
	def _and_or_linker(self,A,and_string=" AND ",end_str=None,start_str=None):
		#for a df of search terms - joins within columns with 'OR', joins 
		#across columns with 'AND'
		dic={}
		for col in A.columns.levels[0]:
			df=A.loc[:,col].dropna()
			dic[col]=" OR ".join(['"'+val[0]+'"' for val in df.values])
		query_string=and_string.join([val for _,val in dic.items()])
		if end_str is not None:
			query_string=query_string+end_str
			
		if start_str is not None:
			query_string=start_str+query_string
		
		return query_string
	
	@staticmethod
	def yamlLoad(path):
	
		with open(path, 'r') as stream:
			try:
				cfg=yaml.load(stream)
			except yaml.YAMLError as exc:
				print(exc)
		return cfg
		
	def search(self,par):
		
		r=requests.get(self.URL, params=par)
		try: 
			assert r.status_code==200
		except AssertionError:
			print('status code error:',r.status_code)
			print(r.json())
			print(r.url)
			raise AssertionError
		
		
		return r
		
	@staticmethod
	def format_response(response):
		return response.json()
	
	
	def get_records(self,response):
		
		new_articles=self.getitem_from_dict(response,self.result_article_key)
		
		try:
			self.articles=self.articles+new_articles
		except AttributeError:
			self.articles=new_articles
		
		return self.articles
		
	def long_search(self,par,max_result=100):
		
	
		r=self.search(par)
		# if self.result_key is not None:
			# result_dic=r.json()[self.result_key]
		# else:
			# result_dic=r.json()
		r=self.format_response(r)
			
		#self.article_count=result_dic[self.result_num_key]
		self.article_count=self.get_article_count(r)
		print(f'there are {self.article_count} articles to retrieve')
		
		self.get_records(r)
		#par=self.update_par_start(par,start_num=len(articles)+1,
		#		response_dic=result_dic,numbers=self.numbers,pages=self.pages)
		
		while len(self.articles)<min(int(self.article_count),max_result):
			
			par=self.update_par_start(par,start_num=len(self.articles)+1, 
				response=r,numbers=self.numbers,pages=self.pages)
			print(par)
			r=self.search(par)
			r=self.format_response(r)
			self.get_records(r)

		print(f'num of articles {len(self.articles)} retrieived, out of total {self.article_count}')
		
		self.articles=self.format_records(self.articles)
		self.raw_header=self.articles.columns.values
		
		return self.articles
		
	def format_records(self,articles):
		return pd.DataFrame(self.articles)
		
	def update_par_start(self,par,start_num=0, response=None,numbers=True,pages=False):
		if pages:
			par[self.page_start]=self.get_next_page(response)
		elif numbers:
			par[self.start_num]=start_num
		return par
		
	def get_next_page(self,response):
		return self.getitem_from_dict(response,self.result_next_page)
		
	def load_par_dic(self,path='lit_search_query_setup.yml',setv=True):
		#from config file, load the mapping to create a search query
		dic=self.yamlLoad(path)
		try:
			our_param=dic[self.key_name]
		except AttributeError:
			print("No 'key_name'set")
			return
			
		
		query_param_terms=dict(standard_dic(**our_param['standard'])._asdict())
		
		if setv: self.query_param_terms=query_param_terms
		if 'additional' in our_param:
			additional_query_param_terms=our_param['additional']
			if setv: self.additional_query_param_terms=additional_query_param_terms
			
			query_param_terms={**query_param_terms,**additional_query_param_terms}
			
		else:
			additional_query_param_terms=None
		
		return query_param_terms, additional_query_param_terms

	def load_query(self,path):
		dic=self.yamlLoad(path)
		dic=dic[self.key_name]
		query=dic.pop('query')
		if dic!={}:
			self.query_param_terms={**self.query_param_terms,**dic}
		return query
		
	def construct_query(self,query):
		#construct the correct query dictionary
		standard=self.standard_dic(query)
		#par_dic=standard._asdict()
		par_dic={self.query_param_terms[k]:standard.__getattribute__(k) for k in standard._fields}
		try:
			add_dic=self.additional_query_param_terms
			par_dic={**par_dic,**add_dic}
		except AttributeError:
			pass
		return self.delete_nones_from_dic(par_dic)
	
	@staticmethod
	def delete_nones_from_dic(dic):
		for k,val in list(dic.items()):
			if val is None:
				dic.pop(k)
		return dic
		
	def get_article_count(self,r):
		return self.getitem_from_dict(r, self.result_num_key)

class LitSearchXML(LitSearch):
	xml=True
	def __init__(self,key_path='lit_review_api.yml',query_setup_path='lit_search_query_setup.yml'):
		super().__init__(key_path=key_path,query_setup_path=query_setup_path)
		self.set_namespaces(query_setup_path)
		self.set_col_dic(query_setup_path)
		
	def set_namespaces(self,query_setup_path):
		dic=self.yamlLoad(query_setup_path)
		self.namespaces=dic[self.key_name]['namespaces']
		
	def set_col_dic(self,query_setup_path):
		dic=self.yamlLoad(query_setup_path)
		self.col_dic=dic[self.key_name]['col_dic']
		

	@staticmethod
	def get_text(thing,listy=False):
	
		def _get_text(t):
			text=t.text
			ans=text
			if text is None:
				attrib=t.attrib
				ans=attrib
			return ans
	
		ans=[_get_text(t) for t in thing]
		
		
		
		if not listy and len(ans)==1: ans=ans[0]
		return ans
	
	@staticmethod
	def format_response(response):
		tree=ET.ElementTree(ET.fromstring(response.content))
		root=tree.getroot()
		return root
	
	
	def get_article_count(self,root):
		article_count=self.get_text(root.findall(self.result_num_key, self.namespaces))
		return article_count
		
	def get_next_page(self,response):
			print('not written yet')
			raise AssertionError
		
	def long_search(self,par,max_result=50):
	

		r=self.search(par)
		r=self.format_response(r)
		#need to get total number of records
		self.article_count=self.get_article_count(r)
		print(f'there are {self.article_count} articles to retrieve')
		
		#need to repeat requests until all records returned
		self.get_records(r)

		
		while len(self.articles)<min(int(self.article_count),max_result):
			
			par=self.update_par_start(par,start_num=len(self.articles)+1, 
				response=r,numbers=self.numbers,pages=self.pages)
			print(par)
			r=self.search(par)
			r=self.format_response(r)
			self.get_records(r)

		print(f'num of articles {len(self.articles)} retrieived, out of total {self.article_count}')

		return self.format_records(self.articles)
		
	
	def get_records(self,root):

		new_articles=root.findall(self.result_article_key,self.namespaces)
		try:
			self.articles=self.articles+new_articles
		except AttributeError:
			self.articles=new_articles
		
		return self.articles
		
	
	def format_records(self,records,col_dic=None,namespaces=None):
		if col_dic is None:
			col_dic=self.col_dic
			
		if namespaces is None:
			namespaces=self.namespaces

		record_list=[]
		for record in records:
			dic={}
			for col, field in col_dic.items():
				dic[col]=self.get_text(record.findall(field, namespaces))
			record_list.append(dic)
			
		return pd.DataFrame(record_list)
		
	def auto_discover_record_columns(records):
	#utility to suggest what the col_dic could be for a record

		listy=[]
		for child in records[0]:
			listy.append((child.tag.split('}')[1],
						  child.tag.split('}')[0].split('{')[1]))

		df=pd.DataFrame(listy)
		df=df.drop_duplicates()
		namespaces=df[1].value_counts().index

		mapper={val:'.//'+str(i)+':' for i,val in zip(range(len(namespaces)),namespaces)}
		namespaces={str(i):val for i,val in zip(range(len(namespaces)),namespaces)}
	   
		
		df['lookup']=df[1].map(mapper)+df[0]
		df=df.set_index(0)
		col_dic=df['lookup'].to_dict()
		return col_dic,namespaces
		
	
class SpringerNatureSearch(LitSearch):
	URL="http://api.springernature.com/metadata/json"
	#URL='http://api.springer.com/metadata/pam'
	key_name='springernature' #this is the title of the api key
	result_num_key= ['result',0,'total'] 
	result_article_key=['records']
	start_num='s'
	
	def query(self,srch_dic=None):
		if srch_dic is None:
			srch_dic=self.search_terms
			
		dic={}
		for k,A in srch_dic.items():
			dic[k]=self._and_or_linker(A,and_string=") AND (",end_str=")",start_str="(")
		return dic
		
	@staticmethod
	def author_get(row):
		
		return [j['creator'] for j in row ]
		
	def format_df(self,r):
		r['authors']=[ self.author_get(i) for i in r.creators]
		r['abstract']=r.abstract.str.split(pat='Abstract',expand=True,n=1)[1]
		r['date']=r['publicationDate']
		r['journal']=r['publicationName']
		r['page']=r['startingPage']
		r['api_source']='Springer Nature'
		r['url']=[k[0]['value'] for k in r.url]
		r['type']=r['contentType']
		
		
		#cols=['title','abstract','authors','date','journal','page','volume','publisher','doi','url','api_source']
		
		return r[self.df_cols]

class ScopusSearch(LitSearch):
	URL="http://api.elsevier.com/content/search/scopus"
	key_name='scopus'
	#result_key='search-results'
	result_num_key=['search-results','opensearch:totalResults']
	result_article_key=['search-results','entry']
	result_next_page=['search-results','cursor','@next']
	
	pages=True
	numbers=False
	start_num='startPage'
	page_start='cursor'
	
	
	def query(self,srch_dic=None):
		if srch_dic is None:
			srch_dic=self.search_terms
			
		dic={}
		for k,A in srch_dic.items():
			dic[k]=self._and_or_linker(A,and_string=" AND ")
		return dic
		
	def format_df(self,r):
		r['title']=r['dc:title']
		try:
			r['abstract']=r['dc:description']
		except KeyError:
			r['abstract']='null'
		r['authors']=[[ a['surname'] if a['given-name'] is None else a['surname']+', '+ a['given-name'] for a in p] for p in r.author]
		r['date']=r['prism:coverDate']
		r['journal']=r['prism:publicationName']
		r['volume']=r['prism:volume']
		r['type']=r['subtypeDescription']

		r['page']=r['prism:pageRange']
		r['publisher']=None
		r['api_source']='Elsevier: Scopus-------------------------------------------------------------------------------------------------------------'
		r['doi']=r['prism:doi']
		r['url']=r['prism:url']

		#cols=['title','type','abstract','authors','date','journal','page','volume','publisher','doi','url','api_source']

		return r[self.df_cols]
		
class ScienceDirectSearch(ScopusSearch):
	URL="https://api.elsevier.com/content/search/sciencedirect"
	key_name='scienceDirect'
	pages=False
	numbers=True
	result_num_key=['search-results','opensearch:totalResults']
	result_article_key=['search-results','entry']
	start_num='start'
	
	@staticmethod
	def author_get(row):
	
		if row is not None and 'author' in row:
			if type(row['author'])==str:
				return row['author']
			elif type(row['author'])==list:
				return [au['$'] for au in row['author']]
		else:
			return None
	
	def format_df(self,r):
		r['title']=r['dc:title']
		try:
			r['abstract']=r['dc:description']
		except KeyError:
			r['abstract']='null'
		r['authors']=[self.author_get(au) for au in r.authors]
		r['date']=r['prism:coverDate']
		r['journal']=r['prism:publicationName']
		r['volume']=r['prism:volume']
		r['type']='null'
		r['page']=r['prism:startingPage'].astype(str)+'-'+r['prism:endingPage'].astype(str)
		r['publisher']=None
		r['api_source']='Elsevier:Science Direct'
		r['doi']=r['prism:doi']
		r['url']=r['prism:url']
		
		return r[self.df_cols]
		
class IEEESearch(LitSearch):
	URL="http://ieeexploreapi.ieee.org/api/v1/search/articles"
	result_num_key=['total_records']
	result_article_key=['articles']
	start_num='start_record'
	key_name='ieeexplore'
	
	def query(self,srch_dic=None):
		if srch_dic is None:
			srch_dic=self.search_terms
			
		dic={}
		for k,A in srch_dic.items():
			dic[k]=self._and_or_linker(A,and_string=") AND (",end_str=")",start_str="(")
		return dic
		
	def format_df(self,r):
		r['abstract']
		r['authors']=[[k['full_name'] for k in r['authors']] for r in r.authors]
		r['date']=r['publication_date']
		r['journal']=r['publication_title']
		r['volume']
		r['type']=r['content_type']
		r['page']=r['start_page']
		r['publisher']
		r['api_source']='IEEE'
		r['doi']
		r['url']=r['pdf_url']
		#cols=['title','type','abstract','authors','date','journal',
			  # 'page','volume','publisher','doi','url','api_source']
		return r[self.df_cols]
		
class ArXivSearch(LitSearchXML):
	#this is an xml returning query
	URL='http://export.arxiv.org/api/query'
	xml=True
	start_num='start'
	key_name='arxiv'
	result_num_key='.//openSearch:totalResults'
	result_article_key='.//atom:entry'
	
	entryrow=namedtuple('entryrow',['title','authors','abstract','date','url','api_source'])


	def format_df(self,r):
		r['abstract']=r['summary']
		r['authors']=r['author']
		r['date']=r['published']
		r['journal']=''
		r['volume']=''
		r['api_source']='ArXiv'
		r['doi']=r['id']
		r['url']=r['id']
		r['publisher']='null'
		r['type']='ArXiv'
		r['page']='null'
		return r[self.df_cols]

		
class PlosSearch(LitSearch):
	
	URL='http://api.plos.org/search'
	start_num='start'
	key_name='plos'
	result_num_key=['response','numFound']
	result_article_key=['response','docs']
	#start_num=['response','start_record']
	
	
	def format_df(self,r):
		r['title']=r['title_display']
		r['abstract']=[p[0] for p in r['abstract'].values]
		r['authors']=r['author_display']
		r['date']=r['publication_date']
		r['journal']=r['journal']
		r['volume']=''
		r['type']=r['article_type']
		r['page']=''
		r['publisher']='PLoS'
		r['api_source']='PLoS'
		r['doi']=''
		r['url']=r['id']
		#cols=['title','type','abstract','authors','date','journal',
			  # 'page','volume','publisher','doi','url','api_source']
		return r[self.df_cols]
		
class WileySearch(LitSearchXML):
	URL='https://onlinelibrary.wiley.com/action/sru'
	key_name='wiley'

	
	result_num_key='.//response:numberOfRecords'
	result_article_key='.//oasis:record'
	
	#define how pagination is handled by api
	pages=False
	numbers=True
	start_num='startRecord'
	

	def format_df(self,r):
		r['source']='Wiley'
		return r
	
class MetaSearch():
	search_types={'springerNature':SpringerNatureSearch,
	'scopus':ScopusSearch,
	'scienceDirect':ScienceDirectSearch,
	'ieee':IEEESearch,
	'arxiv':ArXivSearch,
	'plos':PlosSearch,
	'wiley':WileySearch}
	
	def __init__(self,search_param_path='search_param.yml',**search_bool_dic):
	
		search_list=[]
		self.assert_keys(search_bool_dic)
		self.search_param_path=search_param_path
		for k,val in search_bool_dic.items():
			if val:
				search_list.append(self.search_types[k])
		self.search_list=search_list
		
	def search(self):
		dic={}
		for search_object in self.search_list:
			print(search_object)
			obj=search_object()
			query=obj.load_query(self.search_param_path)
			par=obj.construct_query(query)
			r=obj.long_search(par,max_result=50)
			dic[obj.key_name]=obj.format_df(r)
		return dic
		
	def assert_keys(self,search_bool_dic):
		assert type(search_bool_dic)==dict
		for k,val in search_bool_dic.items():
			assert k in self.search_types.keys()
			assert type(val)==bool

	
	