# CAMSS Utilities

## <center>Transformation of the CAMSS Assessments, from spread-sheets to RDF-OWL</center>
<center><img src="./doc/art/CAMSS Logo landscape.png"/></center>
<center>European Commission, ISA2 Programme, DIGIT</center>
<center><a href="mailto:camss@everis.com">camss@everis.nttdata.com</a></center>
<center><a href="https://joinup.ec.europa.eu/collection/eupl/about">UPL Licence</a><center>
<center>Build 20210415T19:35</center>
<center>Version 0.1</center>

### I. Extraction of the CAMSS Assessments into 'flattened' CSV files, one per Assessment

1. Use the parameter '_--xa-in_' to indicate the directory containing the corpus of CAMSS Assessments as spread-sheets (as XLS, XLSM, or ODS);
2. Use the parameter '_--xa-out_' to indicate where to accumulate the generated flattened CSV files. If the directory and sub-directories indicated do not exist they will be created automatically.

>>> import camss
>>> camss.run({'--xa-in': './in/ass', '--xa-out': './out/ass/csv'})
   
## II. Population of the CAMSS Knowldege Graph with the CAMSS Assessments 

The Assessments are converted to RDF-OWL, one TTL file per Assessment. 
A Graph is created with the prefix and namespace _@prefix camssa: \<http://data.europa.eu/2sa/assessments/>._

<u>usage</u>:

1. Use the parameter '_--ta-in_' to indicate the directory containing the flattened CSV CAMSS Assessments resulting from the extraction (performed in the previous step);
2. Use the parameter '_--ta-out_' to indicate where to accumulate the generated Turtle (TTL) files. If the directory and sub-directories indicated do not exist they will be created automatically.

>>> import camss
>>> camss.run({'--ta-in': './out/ass/csv', '--ta-out': './out/ass/ttl'})

## III. Population of the CAMSS Knowldege Graph with the CAMSS Scenarios and Criteria 

The Assessments, once flattened as CSV files, are used to extract the scenario and criteria existing and 
populate the CAMSS Knowledge Graph with them. 

The graph used to keep scenarios and criteria uses the prefix and namespace _@prefix sc: \<http://data.europa.eu/2sa/scenarios#>._

<u>usage</u>:

1. Use the parameter '_--tc-in_' to indicate the directory containing the flattened CSV CAMSS Assessments resulting from the extraction (performed in the previous step);
2. Use the parameter '_--tc-out_' to indicate where to accumulate the generated Turtle (TTL) files. If the directory and sub-directories indicated do not exist they will be created automatically.

>>> import camss
>>> camss.run({'--tc-in': './out/ass/csv', '--tc-out': './out/crit/ttl'})

## IV. Population of the CAMSS Knowledge Graph with the Specifications and Standards identified by the CAMSS Team

The Assessments, once flattened as CSV files, are used to extract the standards and specifications existing and 
populate the CAMSS Knowledge Graph with them. 

The graph used to keep specifications and standards uses the prefix and namespace _@prefix sc: \<@prefix rsc: <http://data.europa.eu/2sa/cssv/rsc/>._

<u>usage</u>:

1. Use the parameter '_--tc-in_' to indicate the directory containing the flattened CSV CAMSS Assessments resulting from the extraction (performed in the previous step);
2. Use the parameter '_--tc-out_' to indicate where to accumulate the generated Turtle (TTL) files. If the directory and sub-directories indicated do not exist they will be created automatically.

>>> import camss
>>> camss.run({'--ts-in': './out/ass/csv', '--ts-out': './out/specs/ttl'})

## V. List of CAMSS Assessments (basic metadata)

The flattened CSV files are used to extract the basic metadata of each Assessment and build a list. This list is saved as a CSV file.

<u>usage</u>:

1. Use the parameter '_--la-in_' to indicate the directory containing the flattened CSV CAMSS Assessments resulting from the extraction (performed in the previous step);
2. Use the parameter '_--la-out_' to indicate the file path name where to save the list.

>>> import camss
>>> camss.run({'--la-in': './out/ass/csv', '--la-out': './out/ass-list.csv'})


## VI. Merging all Assessment-TTL files into one single OWL-TTL file 

The individual Assessment TTL files, produced after extraction, are merged in one single TTL file.

<u>usage</u>:

1. Use the parameter '_--ga-in_' to indicate the directory containing the TTL CAMSS Assessments;
2. Use the parameter '_--ga-out_' to indicate the file path name where to save the result of the merging.

>>> import camss
>>> camss.run({'--ga-in': './out/ass/ttl', '--ga-out': './out/ass/ass-graph.ttl'})

## VII. Merging all scenario and criteria-TTL files into one single OWL-TTL file 

The individual scenarios and criteria TTL files, produced after extraction, are merged in one single TTL file.

<u>usage</u>:

1. Use the parameter '_--ga-in_' to indicate the directory containing the TTL CAMSS Assessments;
2. Use the parameter '_--ga-out_' to indicate the file path name where to save the result of the merging.

>>> import camss
>>> camss.run({'--ga-in': './out/crit/ttl', '--ga-out': './out/crit/crit-graph.ttl'})

## VIII. Merging all specification-TTL files into one single OWL-TTL file 

The individual specification TTL files, produced after extraction, are merged in one single TTL file.

<u>usage</u>:

1. Use the parameter '_--ga-in_' to indicate the directory containing the TTL CAMSS Assessments;
2. Use the parameter '_--ga-out_' to indicate the file path name where to save the result of the merging.

>>> import camss
>>> camss.run({'--ga-in': './out/specs/ttl', '--ga-out': './out/specs/specs-graph.ttl'})


