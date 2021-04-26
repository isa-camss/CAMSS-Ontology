import os
import re
import sys
import glob
import getopt
import uuid
import ntpath
import hashlib
import datetime
import pandas as p
import logging
from enum import Enum
from pathlib import Path, PurePath
from rdflib import URIRef, Literal, Namespace, Graph
from rdflib.namespace import RDF, SKOS, OWL, DCTERMS, XSD


"""
OOP code 
"""


class ToolVersion(Enum):
    v1_0 = '1.0'
    v2_0_0 = '2.0.0'
    v3_0_0 = '3.0.0'
    v3_1_0 = '3.1.0'


class Assessment:
    """
    Extracts the basic data from one CAMSS Assessment spread-sheet book.
    """
    tv: str
    scenario: str
    title: str  # The title of the specification identifies the Assessment
    ass_filename: str
    ass_file_path: str
    ass_df: p.DataFrame
    id: str
    ss: p.ExcelFile
    book: p.ExcelFile

    MSP_300_TOOLKIT_VERSION_LINE_NUMBER = 13
    MSP_300_COL_DATA_ID = 'Unnamed: 4'

    def __init__(self, file_path: str = None, filename: str = None):

        self.ass_file_path = file_path
        self.ass_filename = filename
        self.tool_version = None
        self.scenario = ''
        self.title = ''
        self.id = ''
        self.book = ''
        self._init()

        return

    def open(self) -> p.ExcelFile:
        """
        Loads the page 0 of an assessment into a Data Frame.
        Please check this page for details on the use of open and sheet:
        https://stackoverflow.com/questions/26521266/using-pandas-to-pd-read-excel-for-multiple-worksheets-of-the-same-workbook
        :return: the book containing the CAMSS Assessment
        """
        self.book = p.ExcelFile(self.ass_file_path)
        self.ass_df = p.read_excel(self.ass_file_path)
        return self.book

    def sheet(self, sheet_name: str) -> p.DataFrame:
        """
        Loads a named page of an assessment into a Data Frame
        Please check this page for details on the use of open and sheet:
        https://stackoverflow.com/questions/26521266/using-pandas-to-pd-read-excel-for-multiple-worksheets-of-the-same-workbook
        :return: the specific book-spread-sheet indicated in the parameter
        """
        self.ass_df = p.read_excel(self.book, sheet_name)
        return self.ass_df

    def _init(self):
        self.open()
        self.get_toolkit_version()
        self.get_scenario()

    def _scenario(self) -> str:
        scenario = None
        if self.tool_version == ToolVersion.v1_0:
            scenario = str(self.ass_df.loc[16, 'Unnamed: 3']).strip()
        elif self.tool_version == ToolVersion.v2_0_0:
            scenario = str(self.ass_df.loc[16, 'Unnamed: 5']).strip()
        elif self.tool_version == ToolVersion.v3_0_0 or self.tool_version == ToolVersion.v3_1_0:
            scenario = str(self.ass_df.loc[18, 'Unnamed: 4']).strip()
        return scenario.strip('\n').strip('.').strip(';').strip()

    def _tool_version(self) -> ToolVersion:
        v1xy = str(self.ass_df.loc[13, 'Unnamed: 0']).strip('\n').strip('.').strip(';').strip()
        v2xy = str(self.ass_df.loc[13, 'Unnamed: 0']).strip('\n').strip('.').strip(';').strip()
        v3xy = str(self.ass_df.loc[13, 'Unnamed: 4']).strip('\n').strip('.').strip(';').strip()

        pattern = re.compile(r"[a-zA-Z]*[:]*[\s]*[\d.]*")
        v1 = pattern.match(v1xy) and '1.' in v1xy
        v2 = pattern.match(v2xy) and '2.' in v2xy
        v3 = pattern.match(v3xy)
        if v1:
            if '1.0' in v1xy:
                self.tool_version = ToolVersion.v1_0
        elif v2:
            if '2.0.0' in v2xy:
                self.tool_version = ToolVersion.v2_0_0
        elif v3:
            if '3.0.0' in v3xy:
                self.tool_version = ToolVersion.v3_0_0
            if '3.1.0' in v3xy:
                self.tool_version = ToolVersion.v3_1_0

        return self.tool_version

    def get_toolkit_version(self) -> ToolVersion:
        self.tool_version = self._tool_version() if not self.tool_version else self.tool_version
        return self.tool_version

    def get_scenario(self) -> str:
        self.scenario = self._scenario() if not self.scenario else self.scenario
        return self.scenario

    def get_date(self) -> str:
        if self.scenario.upper() == 'MSP' and self.tool_version == ToolVersion.v3_0_0:
            self.sheet('Assessment_MSP')
            return self.ass_df.loc[0, 'Unnamed: 6']  # date of the assessment
        elif self.scenario.upper() == 'EIF' and (self.tool_version == ToolVersion.v3_0_0
                                                 or self.tool_version == ToolVersion.v3_1_0):
            self.sheet('Assessment_EIF')
            return self.ass_df.loc[0, 'Unnamed: 4']  # date of the assessment

    def get_title(self) -> str:
        if self.tool_version == ToolVersion.v1_0:
            self.sheet('CAMSS Proposal')
            self.title = self.ass_df.loc[1, 'Unnamed: 8']
        if self.tool_version == ToolVersion.v2_0_0 and self.scenario == 'MSP':
            self.sheet('Setup_MSP')
            self.title = self.ass_df.loc[22, 'Unnamed: 7']
        elif self.tool_version == ToolVersion.v3_0_0 and self.scenario == 'MSP':
            self.sheet('Setup_MSP')
            self.title = self.ass_df.loc[21, 'Unnamed: 7']
        elif self.scenario == 'EIF' and (self.tool_version == ToolVersion.v3_0_0
                                         or self.tool_version == ToolVersion.v3_1_0):
            self.sheet('Setup_EIF')
            self.title = self.ass_df.loc[35, 'Unnamed: 7']
        return self.title.strip('\n').strip('.').strip(';').strip()

    def get_id(self) -> str:
        """
        Creates a unique identifier for this assessment.
        :return: Returns a SHA-256 hash of the concatenation of 'scenario + toolkit_version + title'
        """
        ret = str(self.get_toolkit_version().value) + self.get_scenario() + self.get_title()
        self.id = sha256(ret)
        return self.id


class Assessments:
    """
    Handles off collections of assessments. E.g., produces the list of assessments with unique ids.
    """
    metadata: []
    CSV_METADATA_COLS = ['ASSESSMENT_ID', 'SCENARIO', 'TOOLKIT_VERSION', 'ASSESSMENT_TITLE', 'ASSESSMENT_DATE']
    corpus_dir: str

    def __init__(self, _in_dir: str):
        self.metadata = []
        # DO NOT slash() the dir, otherwise the recursive parsing takes the slash as file and iterates as many times
        # as nesting exists inside the directory.
        self.corpus_dir = _in_dir.strip('/')

    def get_ass_metadata_list(self) -> []:
        """
        Given a corpus of assessments, returns the basic metadata about the assessments contained therein
        :return: A vector with the basic metadata of each assessment found in the corpus
        """
        for index, file_pathname, filename, _ in get_files(self.corpus_dir):
            log(f'{index}. Processing file {file_pathname} ...', nl=False)
            # ass = Assessment(file_path=file_pathname, filename=filename)
            csv = _CSV(file_pathname=file_pathname, filename=filename)
            md = [csv.ass_id, csv.scenario, csv.tool_version, csv.ass_title, csv.ass_date]
            # md = ass.get_id(), ass.get_scenario(), ass.get_toolkit_version().value, ass.get_title(), ass.get_date()]
            self.metadata.append(md)
            print(f'Done!')
        return self.metadata

    def to_csv(self, out_file_pathname: str) -> str:
        data = self.get_ass_metadata_list()
        os.makedirs(ntpath.split(out_file_pathname)[0], exist_ok=True)
        df = p.DataFrame(data=data, columns=self.CSV_METADATA_COLS)
        df.to_csv(out_file_pathname, index=False)
        return out_file_pathname


class _CSV:
    """
    Holds the basic data of the metadata of a CSV after having opened it.
    """

    df: p.DataFrame
    path_name: str
    filename: str
    file_pathname: str
    scenario: str
    tool_version: str
    ass_id: str
    ass_date: str
    ass_title: str

    def __init__(self, file_pathname: str, filename: str):
        self.filename: str = filename
        self.file_pathname = file_pathname
        self.df = self.open()
        self.scenario = self.df.loc[0, 'scenario']
        self.tool_version = self.df.loc[0, 'tool_version']
        self.ass_id = self.df.loc[0, 'assessment_id']
        self.ass_title = self.df.loc[0, 'assessment_title']
        self.ass_date = self.df.loc[0, 'assessment_date']

    def open(self) -> p.DataFrame:
        return p.read_csv(self.file_pathname)


class Extractor:
    """
    Extracts the data of an Assessment from a CAMSS solution (e.g., a complex book of spread-sheets)
    """
    in_df: p.DataFrame      # The Dataframe of the the current Assessment, contains the input data
    ass: Assessment         # The Assessment being currently processed
    version: ToolVersion    # Current Assessment Toolkit Version
    metadata: dict          # Assessment metadata
    criteria: list          # Assessment criteria

    def __init__(self, ass: Assessment):
        self.ass = ass
        self.in_df = self.ass.ass_df
        self.version = self.ass.tool_version
        self.metadata: dict = {}
        self.criteria: list = []

    @staticmethod
    def _eif_choice(option: str) -> int:
        """
        Transforms X into 0 (False), ✓ into 1 (True), and N/A into 2 (None)
        :param option: the string ✓, X, or nan
        :return:
        """
        o = option.strip().lower()
        if o == '✓':
            return 1
        elif o == 'x':
            return 0
        elif o == 'nan':
            return 2

    @staticmethod
    def _msp_choice(option: str) -> int:
        """
        Transforms YES or NO into 1 (True) or 0 (False)
        :param option: the string YES or NO
        :return: 0 or 1, 2 means n/a or unknown
        """
        o = option.strip().lower()
        if o == 'yes':
            return 1
        elif o == 'no':
            return 0
        else:
            return 2

    @staticmethod
    def _reformat_date(rd: str) -> str:
        rd = rd[len(rd) - 10:]
        try:
            rd = str(datetime.datetime.strptime(rd, "%d/%m/%Y").strftime("%Y-%m-%d"))
        except:
            pass
        return rd

    def _build_data(self) -> []:
        data = []
        for criterion in self.criteria:
            md = list(self.metadata.values())
            data.append(md + criterion)
        return data

    def _get_basic_metadata(self):
        """
        The following metadata is common to all versions, calculated in th Assessment class
        :return: nothing
        """
        self.metadata['assessment_id'] = self.ass.get_id()
        self.metadata['assessment_title'] = self.ass.get_title()
        self.metadata['tool_version'] = str(self.version.value)
        return

    def _get_eif_3x_metadata(self):
        # 'rd' stands for release date
        rd = self.in_df.loc[14, 'Unnamed: 4']
        self.metadata['tool_release_date'] = rd[len(rd) - 10:]
        self.metadata['scenario'] = self.in_df.loc[18, 'Unnamed: 4'].strip()
        self.metadata['scenario_purpose'] = self.in_df.loc[28, 'Unnamed: 1'].strip()
        # Setup_EIF
        self.in_df = self.ass.sheet('Setup_EIF')
        self.metadata['submitter_unit_id'] = sha256(str(self.in_df.loc[5, 'Unnamed: 7']))  # Submitter_id
        self.metadata['L1'] = self.in_df.loc[5, 'Unnamed: 7']                  # Submitter_name *
        self.metadata['submitter_org_id'] = sha256(str(self.in_df.loc[7, 'Unnamed: 7']))  # submitter_organisation_id
        self.metadata['L2'] = self.in_df.loc[7, 'Unnamed: 7']                  # submitter_organisation
        self.metadata['L3'] = self.in_df.loc[9, 'Unnamed: 7']                  # submitter_role
        self.metadata['L4'] = self.in_df.loc[11, 'Unnamed: 7']                 # submitter_address
        self.metadata['L5'] = self.in_df.loc[13, 'Unnamed: 7']                 # submitter_phone
        self.metadata['L6'] = self.in_df.loc[15, 'Unnamed: 7']                 # submitter_email
        self.metadata['L7'] = self.in_df.loc[17, 'Unnamed: 7']                 # submission_date
        sc_id = sha256(str(self.in_df.loc[19, 'Unnamed: 7']) + '-' + str(self.metadata['tool_version']))
        self.metadata['scenario_id'] = sc_id
        self.metadata['L8'] = self.in_df.loc[19, 'Unnamed: 7']                 # scenario
        self.metadata['spec_id'] = sha256(str(self.in_df.loc[35, 'Unnamed: 7']))  # spec_id, the MD5 of the title
        self.metadata['distribution_id'] = str(uuid.uuid4())                   # distribution_id
        self.metadata['P1'] = self.in_df.loc[35, 'Unnamed: 7']                 # spec_title
        self.metadata['P2'] = self.in_df.loc[37, 'Unnamed: 7']                 # spec_download_url
        self.metadata['sdo_id'] = sha256(str(self.in_df.loc[39, 'Unnamed: 7']))  # sdo_id (for the Agent instance)
        self.metadata['P3'] = self.in_df.loc[39, 'Unnamed: 7']                 # sdo_name
        self.metadata['P4'] = self.in_df.loc[41, 'Unnamed: 7']                 # sdo_contact_point
        self.metadata['P5'] = self.in_df.loc[43, 'Unnamed: 7']                 # submission_rationale
        self.metadata['P6'] = self.in_df.loc[45, 'Unnamed: 7']                 # other_evaluations
        # The following 'Pn' are necessary to build a harmonised CSV that can be later be transformed in the same
        # way. These additional 'Ps' come from the MSP_300 version
        self.metadata['P7'] = ''
        self.metadata['P8'] = ''
        self.metadata['P9'] = ''
        self.metadata['P10'] = ''
        # Considerations
        self.metadata['C1'] = self.in_df.loc[93, 'Unnamed: 7']                 # correctness
        self.metadata['C2'] = self.in_df.loc[95, 'Unnamed: 7']                 # completeness
        self.metadata['C3'] = self.in_df.loc[97, 'Unnamed: 7']                 # egov_interoperability
        # These other 'Cn' are defined in MSP_300,thus we need to add then to harmonise the CSV
        self.metadata['C4'] = ''
        self.metadata['C5'] = ''
        # Open Criteria page, which name is common for all EIF_3x: 'Assessment_EIF'
        self.in_df = self.ass.sheet('Assessment_EIF')
        self.metadata['assessment_date'] = self.in_df.loc[0, 'Unnamed: 4']  # date of the assessment
        self.metadata['io_spec_type'] = self.in_df.loc[8, 'Unnamed: 4']  # interoperability specification type
        return

    def _add_eif_3x_criterion(self, init: int, end: int, line: int, line_step: int):
        """
                Builds a vector with groups of criteria
                :param init: line + init sets which row to read
                :param end: line + end sets the last row to read (not included)
                :param line: the row of the dataframe where to start grouping
                :param line_step: the offset between lines, sometimes 2, sometimes 4,etc. depending on the groups
                and subgroups of principle and groups between criteria.
                :return: nothing, values are kept into a class-scoped vector
                """
        for i in range(init, end):
            criterion = []
            element = 'A' + str(i)
            # Assessment Criterion ID
            criterion.append(element)
            # SHA Criterion ID
            criterion.append(sha256(str(self.in_df.loc[line, 'Unnamed: 2'])))
            # Criterion Description
            criterion.append(str(self.in_df.loc[line, 'Unnamed: 2']))
            # Score element ID and Value
            criterion.append(str(uuid.uuid4()))
            criterion.append(self._eif_choice(str(self.in_df.loc[line, 'Unnamed: 6'])))
            # Criterion Justification Id and Judgement text
            criterion.append(str(uuid.uuid4()))
            criterion.append(self.in_df.loc[line, 'Unnamed: 8'])
            line += line_step
            self.criteria.append(criterion)
        return

    def _get_eif_300_criteria(self):
        # Criteria
        self._add_eif_3x_criterion(init=1, end=2, line=16, line_step=2)
        # OPENNESS
        self._add_eif_3x_criterion(init=2, end=11, line=22, line_step=2)
        # TRANSPARENCY
        self._add_eif_3x_criterion(init=11, end=13, line=42, line_step=2)
        # REUSABILITY
        self._add_eif_3x_criterion(init=13, end=15, line=48, line_step=2)
        # # TECHNOLOGICAL NEUTRALITY
        self._add_eif_3x_criterion(init=15, end=18, line=54, line_step=2)
        # USER CENTRICITY
        # INCLUSION AND ACCESSIBILITY
        # SECURITY AND PRIVACY
        # MULTILINGUALISM
        self._add_eif_3x_criterion(init=18, end=22, line=64, line_step=4)
        # ADMINISTRATIVE SIMPLIFICATION
        # PRESERVATION OF INFORMATION
        # ASSESSMENT OF EFFECTIVENESS AND EFFICIENCY
        self._add_eif_3x_criterion(init=22, end=25, line=82, line_step=4)
        # INTEROPERABILITY GOVERNANCE
        self._add_eif_3x_criterion(init=25, end=31, line=96, line_step=2)
        # INTEGRATED PUBLIC SERVICE GOVERNANCE
        # LEGAL INTEROPERABILITY
        self._add_eif_3x_criterion(init=31, end=33, line=110, line_step=4)
        # ORGANISATIONAL INTEROPERABILITY
        self._add_eif_3x_criterion(init=33, end=35, line=121, line_step=2)
        # SEMANTIC INTEROPERABILITY
        self._add_eif_3x_criterion(init=35, end=38, line=127, line_step=2)
        return

    def _get_eif_310_criteria(self):
        # Criteria
        self._add_eif_3x_criterion(init=1, end=2, line=16, line_step=2)
        # OPENNESS
        self._add_eif_3x_criterion(init=2, end=12, line=22, line_step=2)
        # TRANSPARENCY
        self._add_eif_3x_criterion(init=12, end=15, line=44, line_step=2)
        # REUSABILITY
        self._add_eif_3x_criterion(init=15, end=18, line=52, line_step=2)
        # # TECHNOLOGICAL NEUTRALITY
        self._add_eif_3x_criterion(init=18, end=21, line=60, line_step=2)
        # USER CENTRICITY
        # INCLUSION AND ACCESSIBILITY
        # SECURITY AND PRIVACY
        # MULTILINGUALISM
        self._add_eif_3x_criterion(init=21, end=25, line=70, line_step=4)
        # ADMINISTRATIVE SIMPLIFICATION
        # PRESERVATION OF INFORMATION
        # ASSESSMENT OF EFFECTIVENESS AND EFFICIENCY
        self._add_eif_3x_criterion(init=25, end=28, line=88, line_step=4)
        # INTEROPERABILITY GOVERNANCE
        self._add_eif_3x_criterion(init=28, end=34, line=102, line_step=2)
        # INTEGRATED PUBLIC SERVICE GOVERNANCE
        # LEGAL INTEROPERABILITY
        self._add_eif_3x_criterion(init=34, end=36, line=116, line_step=4)
        # ORGANISATIONAL INTEROPERABILITY
        self._add_eif_3x_criterion(init=36, end=38, line=127, line_step=2)
        # SEMANTIC INTEROPERABILITY
        self._add_eif_3x_criterion(init=38, end=40, line=133, line_step=2)
        return

    def _get_msp_300_metadata(self):
        # 'rd' stands for release date
        rd = self.in_df.loc[14, 'Unnamed: 4']
        self.metadata['tool_release_date'] = rd[len(rd) - 10:]
        self.metadata['scenario'] = self.in_df.loc[18, 'Unnamed: 4'].strip()
        self.metadata['scenario_purpose'] = self.in_df.loc[28, 'Unnamed: 1'].strip()
        # Setup_MSP
        self.in_df = self.ass.sheet('Setup_MSP')
        self.metadata['submitter_unit_id'] = sha256(str(self.in_df.loc[5, 'Unnamed: 7']))  # Submitter_id
        self.metadata['L1'] = self.in_df.loc[5, 'Unnamed: 7']  # Submitter_name *
        self.metadata['submitter_org_id'] = sha256(str(self.in_df.loc[7, 'Unnamed: 7']))  # submitter_organisation_id
        self.metadata['L2'] = self.in_df.loc[7, 'Unnamed: 7']  # submitter_organisation
        self.metadata['L3'] = self.in_df.loc[9, 'Unnamed: 7']  # submitter_role
        self.metadata['L4'] = self.in_df.loc[11, 'Unnamed: 7']  # submitter_address
        self.metadata['L5'] = self.in_df.loc[13, 'Unnamed: 7']  # submitter_phone
        self.metadata['L6'] = self.in_df.loc[15, 'Unnamed: 7']  # submitter_email
        self.metadata['L7'] = str(self.in_df.loc[17, 'Unnamed: 7'])  # submission_date
        sc_id = sha256(str(self.in_df.loc[19, 'Unnamed: 7']) + '-' + str(self.metadata['tool_version']))
        self.metadata['scenario_id'] = sc_id
        # self.metadata['scenario_id'] = sha256(str(self.in_df.loc[19, 'Unnamed: 7']))  # scenario_id
        self.metadata['spec_id'] = sha256(str(self.in_df.loc[21, 'Unnamed: 7']))  # spec_id, the MD5 of the title
        self.metadata['distribution_id'] = str(uuid.uuid4())  # distribution_id
        self.metadata['P1'] = self.in_df.loc[21, 'Unnamed: 7']  # spec_title
        self.metadata['P2'] = self.in_df.loc[23, 'Unnamed: 7']  # spec_download_url
        self.metadata['sdo_id'] = sha256(str(self.in_df.loc[25, 'Unnamed: 7']))  # sdo_id (for the Agent instance)
        self.metadata['P3'] = self.in_df.loc[25, 'Unnamed: 7']  # sdo_name
        self.metadata['P4'] = self.in_df.loc[27, 'Unnamed: 7']  # sdo_contact_point
        self.metadata['P5'] = self.in_df.loc[29, 'Unnamed: 7']  # submission_rationale
        self.metadata['P6'] = self.in_df.loc[31, 'Unnamed: 7']  # any other evaluation of this spec known
        self.metadata['P7'] = self.in_df.loc[33, 'Unnamed: 7']  # submission scope
        self.metadata['P8'] = self.in_df.loc[35, 'Unnamed: 7']  # backward and forward compatibility
        self.metadata['P9'] = self.in_df.loc[37, 'Unnamed: 7']  # no longer compliance
        self.metadata['P10'] = self.in_df.loc[39, 'Unnamed: 7']  # first SDO spec?
        self.metadata['C1'] = self.in_df.loc[45, 'Unnamed: 7']  # correctness
        self.metadata['C2'] = self.in_df.loc[47, 'Unnamed: 7']  # completeness
        self.metadata['C3'] = self.in_df.loc[51, 'Unnamed: 7']  # egov_interoperability
        self.metadata['C4'] = self.in_df.loc[53, 'Unnamed: 7']  # egov_interoperability
        self.metadata['C5'] = self.in_df.loc[57, 'Unnamed: 7']  # egov_interoperability
        # Open Criteria page: 'Assessment_MSP'
        # Assessment_MSP
        self.in_df = self.ass.sheet('Assessment_MSP')
        self.metadata['assessment_date'] = self.in_df.loc[0, 'Unnamed: 6']  # date of the assessment
        self.metadata['io_spec_type'] = self.in_df.loc[8, 'Unnamed: 6']  # interoperability specification type
        return

    def _add_msp_300_criterion(self, init: int, end: int, line: int, line_step: int):
        """
        Builds a vector with groups of criteria
        :param init: line + init sets which row to read
        :param end: line + end sets the last row to read (not included)
        :param line: the row of the dataframe where to start grouping
        :param line_step: the offset between lines, sometimes 2, sometimes 4,etc. depending on the groups and subgroups
        of principle and groups between criteria.
        :return: nothing, values are kept into a class-scoped vector
        """
        element = ''
        for i in range(init, end):
            # In certain versions of the spreadsheet, some criteria were defined but hidden, e.g. criterion 5c.
            # In those cases we simply do not add the criterion, since there will not be any valid answer, and
            # capturing a value n/a would alter the strength of the assessment.
            no_answer = str(self.in_df.loc[line, 'Unnamed: 8']) == 'nan'
            if no_answer:
                continue
            criterion = []
            element = element if str(self.in_df.loc[line, 'Unnamed: 2']) == 'nan' \
            else str(self.in_df.loc[line, 'Unnamed: 2'])
            sub_element = '' if str(self.in_df.loc[line, 'Unnamed: 3']) == 'nan' \
            else str(self.in_df.loc[line, 'Unnamed: 3'])
            # Assessment Criterion ID
            criterion.append(element + sub_element)
            # SHA Criterion ID
            criterion.append(sha256(str(self.in_df.loc[line, 'Unnamed: 4'])))
            # Criterion description
            criterion.append(self.in_df.loc[line, 'Unnamed: 4'])
            # Score element ID and Value
            criterion.append(str(uuid.uuid4()))
            criterion.append(self._msp_choice(str(self.in_df.loc[line, 'Unnamed: 8'])))
            # Criterion Justification Id and Judgement text
            criterion.append(str(uuid.uuid4()))
            criterion.append(self.in_df.loc[line, 'Unnamed: 10'])
            line += line_step
            self.criteria.append(criterion)
        return

    def _get_msp_300_criteria(self):
        # The sheet has been opened whilst capturing metadata
        # Criteria
        # MARKET ACCEPTANCE
        self._add_msp_300_criterion(init=1, end=4, line=14, line_step=2)
        # COHERENCE PRINCIPLE
        self._add_msp_300_criterion(init=14, end=18, line=22, line_step=2)
        # ATTRIBUTES
        self._add_msp_300_criterion(init=18, end=19, line=32, line_step=2)
        # ATTRIBUTES.OPENNESS
        self._add_msp_300_criterion(init=19, end=20, line=36, line_step=2)
        # ATTRIBUTES.CONSENSUS
        self._add_msp_300_criterion(init=36, end=37, line=40, line_step=2)
        # ATTRIBUTES.TRANSPARENCY
        self._add_msp_300_criterion(init=37, end=40, line=44, line_step=2)
        # ATTRIBUTES.TRANSPARENCY
        self._add_msp_300_criterion(init=37, end=40, line=44, line_step=2)
        # REQUIREMENTS
        # REQUIREMENTS.MAINTENANCE
        self._add_msp_300_criterion(init=40, end=41, line=54, line_step=2)
        # REQUIREMENTS.AVAILABILITY
        self._add_msp_300_criterion(init=41, end=42, line=58, line_step=2)
        # REQUIREMENTS.INTELLECTUAL PROPERTY
        self._add_msp_300_criterion(init=42, end=44, line=62, line_step=2)
        # REQUIREMENTS.RELEVANCE
        self._add_msp_300_criterion(init=44, end=46, line=68, line_step=2)
        # REQUIREMENTS.NEUTRALITY AND STABILITY
        self._add_msp_300_criterion(init=46, end=48, line=74, line_step=2)
        # REQUIREMENTS.QUALITY
        self._add_msp_300_criterion(init=48, end=49, line=80, line_step=2)
        return

    def extract(self) -> []:
        self._get_basic_metadata()
        if self.ass.scenario == 'EIF':
            if self.ass.tool_version == ToolVersion.v3_1_0 or self.ass.tool_version == ToolVersion.v3_0_0:
                self._get_eif_3x_metadata()
            if self.ass.tool_version == ToolVersion.v3_1_0:
                self._get_eif_310_criteria()
            if self.ass.tool_version == ToolVersion.v3_0_0:
                self._get_eif_300_criteria()
        elif self.ass.scenario == 'MSP':
            if self.ass.tool_version == ToolVersion.v3_0_0:
                self._get_msp_300_metadata()
                self._get_msp_300_criteria()

        return self._build_data()

    def to_csv(self, out_file_pathname) -> str:
        data = self.extract()
        if data and len(data) > 0:
            columns = list(self.metadata.keys()) + \
                      ['criterion_camss_id',
                       'criterion_sha_id',
                       'criterion_description',
                       'score_id',
                       'score',
                       'statement_id',
                       'statement']
            with open(out_file_pathname, 'w') as f:
                p.DataFrame(data=data, columns=columns).to_csv(f, index=False)
            return out_file_pathname


"""
AssTransformer class: takes a CSV-flattened Assessment and converts it into an RDF Graph.
"""

# Namespaces
CAMSS = Namespace("http://data.europa.eu/2sa#")
CAMSSA = Namespace("http://data.europa.eu/2sa/assessments/")
CAV = Namespace("http://data.europa.eu/2sa/cav#")
CCCEV = Namespace("http://data.europa.eu/m8g/cccev#")
CSSV = Namespace("http://data.europa.eu/2sa/cssv#")
CSSV_RSC = Namespace("http://data.europa.eu/2sa/cssv/rsc/")
DCAT = Namespace("http://www.w3.org/ns/dcat#")
DCT = Namespace
ORG = Namespace("http://www.w3.org/ns/org#")
SC = Namespace("http://data.europa.eu/2sa/scenarios#")
SCHEMA = Namespace("http://schema.org/")
STATUS = Namespace("http://data.europa.eu/2sa/rsc/assessment-status#")
TOOL = Namespace("http://data.europa.eu/2sa/rsc/toolkit-version#")


class GraphWorker:
    g: Graph
    df: p.DataFrame
    ttl_filename: str
    csv: _CSV

    def __init__(self, csv: _CSV = None, graph: Graph = None):
        """
        Helpers for common operations executed by the CSV to Graph transformers
        """
        self.g = graph
        self.csv = csv
        self.df = self.csv.df if csv else None
        self.ttl_filename = ''
        # IO SPEC TITLE
        return

    def set_ttl_filename(self, ttl: str):
        self.ttl_filename = ttl
        return

    def serialize(self) -> str:
        # Remove previous version
        try:
            os.remove(self.ttl_filename)
        except OSError:
            pass
        # Save to file
        self.g.serialize(format="turtle", destination=self.ttl_filename)
        return self.ttl_filename

    def merge(self, sub_graph: Graph) -> Graph:
        """
        Merges the sub_graph into the Wprkers' default self.g graph)
        :param self: this Worker's instance
        :param sub_graph: the graph to be subsumed into the default graph of this Worker
        :return: the larger graph resulting from the merging
        """
        self.g.parse(sub_graph, format='ttl')
        return self.g


class AssTransformer(GraphWorker):

    def __init__(self, csv: _CSV):
        super(AssTransformer, self).__init__(csv)

    def _create_graph(self, name: str = None, base: str = None) -> Graph:
        self.g = Graph(identifier=name, base=base)
        self.g.bind('skos', SKOS)
        self.g.bind('dct', DCTERMS)
        self.g.bind('owl', OWL)
        self.g.bind('org', ORG)
        self.g.bind('schema', SCHEMA)
        self.g.bind('camss', CAMSS)
        self.g.bind('cav', CAV)
        self.g.bind('cssv', CSSV)
        self.g.bind('camssa', CAMSSA)
        self.g.bind('cssvrsc', CSSV_RSC)
        self.g.bind('status', STATUS)
        self.g.bind('tool', TOOL)
        self.g.bind('sc', SC)
        return self.g

    def _add_assessment(self, row: p.Series) -> Graph:
        ass_uri = URIRef(CAMSSA + row['assessment_id'], CAMSSA)
        self.g.add((ass_uri, RDF.type, CAV.Assessment))
        self.g.add((ass_uri, RDF.type, OWL.NamedIndividual))
        title: str = str(row['assessment_title'])
        self.g.add((ass_uri, DCTERMS.title, Literal(title, lang='en')))
        self.g.add((ass_uri, CAMSS.toolVersion, URIRef(TOOL + row['tool_version'], TOOL)))
        self.g.add((ass_uri, CAV.contextualisedBy, URIRef(SC + row['scenario_id'], SC)))
        self.g.add((ass_uri, CAMSS.assesses, URIRef(CSSV_RSC + row['spec_id'], CSSV_RSC)))
        self.g.add((ass_uri, CAV.status, STATUS.Complete))
        self.g.add((ass_uri, CAMSS.submissionDate, Literal(row['L7'], datatype=XSD.date)))
        self.g.add((ass_uri, CAMSS.assessmentDate, Literal(row['assessment_date'], datatype=XSD.date)))
        return self.g

    def _add_assessor(self, row: p.Series) -> Graph:
        uri_assessor = URIRef(CAMSSA + row['submitter_org_id'], CAMSSA)
        self.g.add((uri_assessor, RDF.type, ORG.Organization))
        self.g.add((uri_assessor, RDF.type, OWL.NamedIndividual))
        self.g.add((uri_assessor, SKOS.prefLabel, Literal(row['L1'], lang='en')))
        # Contact Point
        cp_uri = URIRef(CAMSSA + str(uuid.uuid4()), CAMSSA)
        self.g.add((uri_assessor, CAMSS.contactPoint, cp_uri))
        self.g.add((cp_uri, RDF.type, SCHEMA.ContactPoint))
        self.g.add((cp_uri, RDF.type, OWL.NamedIndividual))
        self.g.add((cp_uri, SCHEMA.email, Literal(row['L6'])))
        return self.g

    def _add_answer(self, row: p.Series) -> Graph:
        """
        Adds the statements and scores provided by the assessor
        :returns: the Graph
        """
        # Score
        score_uri = URIRef(CAMSSA + row['score_id'], CAMSSA)
        self.g.add((score_uri, RDF.type, CAV.Score))
        self.g.add((score_uri, RDF.type, OWL.NamedIndividual))
        self.g.add((score_uri, CAV.value, Literal(row['score'], datatype=XSD.int)))
        self.g.add((score_uri, CAV.assignedTo, URIRef(SC + 'c-' + row['criterion_sha_id'], SC)))
        # Statement
        statement_uri = URIRef(CAMSSA + row['statement_id'], CAMSSA)
        self.g.add((statement_uri, RDF.type, CAV.Statement))
        self.g.add((statement_uri, RDF.type, OWL.NamedIndividual))
        self.g.add((statement_uri, CAV.refersTo, score_uri))
        self.g.add((statement_uri, CAV.judgement, Literal(row['statement'], lang='en')))
        # Assessment
        ass_uri = URIRef(CAMSSA + row['assessment_id'], CAMSSA)
        self.g.add((ass_uri, CAV.resultsIn, statement_uri))
        return self.g

    def transform(self) -> Graph:
        row = self.df.iloc[0]
        self._add_assessment(row)
        self._add_assessor(row)
        for index, row in self.df.iterrows():
            self._add_answer(row)
        return self.g

    def to_ttl(self, ta_out) -> str:
        self.ttl_filename = ta_out
        self._create_graph(CAMSSA)
        self.transform()
        return super().serialize()


class CritTransformer(GraphWorker):
    """
    Gets the scenarios and criteria of an Assessment CSV flattened file and converts it into an RDF Graph.
    """
    def __init__(self, csv: _CSV):
        super(CritTransformer, self).__init__(csv)

    def _create_graph(self, name: str = None, base: str = None) -> Graph:
        self.g = Graph(identifier=name, base=base)
        self.g.bind('skos', SKOS)
        self.g.bind('dct', DCTERMS)
        self.g.bind('owl', OWL)
        self.g.bind('camss', CAMSS)
        self.g.bind('cav', CAV)
        self.g.bind('sc', SC)
        self.g.bind('cccev', CCCEV)
        return self.g

    def _add_scenario(self, row: p.Series) -> URIRef:
        sc_uri = URIRef(SC + str(row['scenario_id']), SC)
        title: str = str(row['scenario']) + '(' + str(row['tool_version'] + ')')
        self.g.add((sc_uri, DCTERMS.title, Literal(title, lang='en')))
        self.g.add((sc_uri, RDF.type, CAV.Scenario))
        self.g.add((sc_uri, RDF.type, OWL.NamedIndividual))
        self.g.add((sc_uri, CAV.purpose, Literal(row['scenario_purpose'], lang='en')))
        self.g.add((sc_uri, CAV.description, Literal(row['scenario_purpose'], lang='en')))
        return sc_uri

    def _add_criterion(self, row: p.Series) -> URIRef:
        uri_criterion = URIRef(SC + row['criterion_sha_id'], SC)
        self.g.add((uri_criterion, RDF.type, CCCEV.Criterion))
        self.g.add((uri_criterion, RDF.type, OWL.NamedIndividual))
        self.g.add((uri_criterion, CCCEV.hasDescription, Literal(row['criterion_description'], lang='en')))
        return uri_criterion

    def _link_criterion_to_scenario(self, sc_uri: URIRef, row: p.Series) -> (URIRef, URIRef):
        crit_uri = self._add_criterion(row)
        self.g.add((sc_uri, CAV.includes, crit_uri))
        return sc_uri, crit_uri

    def transform(self) -> Graph:
        row = self.df.iloc[0]
        sc_uri = self._add_scenario(row)
        for index, row in self.df.iterrows():
            self._link_criterion_to_scenario(sc_uri, row)
        return self.g

    def to_ttl(self, ttl_file_pathname) -> str:
        self.ttl_filename = ttl_file_pathname
        self._create_graph(CAMSS)
        self.transform()
        return super().serialize()


class SpecTransformer(GraphWorker):
    """
    Gets the data related to a specification from a CAMSS Assessment and saves the data into an RDF Graph.
    """
    def __init__(self, csv: _CSV):
        super(SpecTransformer, self).__init__(csv)

    def _create_graph(self, name: str = None, base: str = None) -> Graph:
        self.g = Graph(identifier=name, base=base)
        self.g.bind('skos', SKOS)
        self.g.bind('dct', DCTERMS)
        self.g.bind('owl', OWL)
        self.g.bind('cssv', CSSV)
        self.g.bind('cssvrsc', CSSV_RSC)
        self.g.bind('dcat', DCAT)
        self.g.bind('xsd', XSD)
        self.g.bind('schema', SCHEMA)
        self.g.bind('org', ORG)

        return self.g

    def _add_distribution(self, row: p.Series) -> URIRef:
        uri_dist = URIRef(CSSV_RSC + str(row['distribution_id']), CSSV_RSC)
        self.g.add((uri_dist, RDF.type, DCAT.Distribution))
        self.g.add((uri_dist, RDF.type, OWL.NamedIndividual))
        self.g.add((uri_dist, DCAT.accessURL, Literal(str(row['P2']), datatype=XSD.anyURI)))
        return uri_dist

    def _add_sdo(self, row: p.Series) -> URIRef:
        uri_agent = URIRef(CSSV_RSC + str(row['sdo_id']), CSSV_RSC)
        self.g.add((uri_agent, RDF.type, ORG.Organization))
        self.g.add((uri_agent, RDF.type, OWL.NamedIndividual))
        # Name and URL of the SDO
        self.g.add((uri_agent, SKOS.prefLabel, Literal(str(row['P3']), datatype=XSD.string)))
        return uri_agent

    def _add_contact_point(self, row: p.Series) -> URIRef:
        uri_cp = URIRef(CSSV_RSC + str(uuid.uuid4()), CSSV_RSC)
        self.g.add((uri_cp, RDF.type, SCHEMA.ContactPoint))
        self.g.add((uri_cp, RDF.type, OWL.NamedIndividual))
        self.g.add((uri_cp, SCHEMA.email, Literal(row['L6'])))
        return uri_cp

    def _add_specification(self, row: p.Series) -> URIRef:
        uri = URIRef(CSSV_RSC + str(row['spec_id']), CSSV_RSC)
        self.g.add((uri, RDF.type, OWL.NamedIndividual))
        st = str(row['io_spec_type']).lower()

        if 'specification' in st or 'nan' in st:
            self.g.add((uri, RDF.type, CSSV.Specification))
        elif 'standard' in st:
            self.g.add((uri, RDF.type, CSSV.Standard))
        elif 'profile' in st:
            self.g.add((uri, RDF.type, CSSV.ApplicationProfile))
        elif 'family' in st:
            self.g.add((uri, RDF.type, CSSV.Family))
        self.g.add((uri, DCTERMS.title, Literal(str(row['P1']), lang='en')))
        return uri

    def transform(self) -> Graph:
        # All the information is available (repeated) in any of the rows, hence let's take the first one only
        row = self.df.iloc[0]
        uri_dist: URIRef = self._add_distribution(row)
        uri_sdo: URIRef = self._add_sdo(row)
        uri_cp: URIRef = self._add_contact_point(row)
        uri_spec: URIRef = self._add_specification(row)
        self.g.add((uri_spec, CSSV.isMaintainedBy, uri_sdo))
        self.g.add((uri_spec, DCAT.distribution, uri_dist))
        self.g.add((uri_cp, CSSV.isContactPointOf, uri_sdo))
        return self.g

    def to_ttl(self, ttl_file_pathname: str) -> str:
        self.ttl_filename = ttl_file_pathname
        self._create_graph(CSSV_RSC)
        self.transform()
        return super().serialize()


"""
Functional code
"""

"""
Utils
"""


def xst_file(path: str) -> bool:
    """
    Checks whether a file or directory exists or not.
    :param path:  the path to the dir or file
    :return: the result of the checking
    """
    return os.path.isdir(path) or os.path.isfile(path)


def get_files(root_dir: str, exclude: [] = None) -> (int, str, str, str):
    """
    Returns lazily and recursively each path file name, the file name, extension and an index number from
    inside the folders of a root folder
    :param root_dir: the initial folder with the directories and files
    :param exclude: list of files or directories to not get into
    :return: file absolute path, file name, extension, and its index number
    """
    exclude = [] if not exclude else exclude
    i: int = 0
    xst_file(root_dir)
    # For every file in the directory structure
    for path in glob.iglob(root_dir + '**/**', recursive=True):
        xpath = PurePath(path)
        if xpath.name not in exclude:
            if os.path.isfile(path) and Path(path).suffix:
                i += 1
                name, ext = file_split_name_ext(get_file_name_from_path(path))
                yield i, path, name, ext


def get_file_name_from_path(path) -> str:
    head, tail = ntpath.split(path)
    return tail or ntpath.basename(head)


def file_split_name_ext(file_name: str) -> (str, str):
    v = os.path.splitext(file_name)
    return v[0], v[1]


def sha256(text: str) -> str:
    """
    Generates a SHA256 hash of a text
    :param text: the text to digest
    :return: the hash as a text
    """
    if text:
        return hashlib.sha256(text.encode()).hexdigest()
    else:
        raise Exception("No sha256-based id generated because no thruty provided.")


def slash(path) -> str:
    """
    Will add the trailing slash if it's not already there.
    :param path: path file name
    :return: slashed path file name
    """
    return os.path.join(path, '')


def __help__():
    print(
        """
        CAMSS Python utilities
        European Commission, ISA2 Programme, DIGIT
        camss@everis.nttdata.com
        contributor: mailto:enric.staromiejski.torregrosa@everis.nttdata.com
        contributor: mailto:juan.carlos.segura.fernandez.carnicero@everis.nttdata.com
        Licence UPL (https://joinup.ec.europa.eu/collection/eupl/about)
        Build 20210415T19:35
        Version 0.1
    
        Command-line syntax:
        -------------------
        
        python camss.py <param_key_1> <option_1> ... <param_key_n> <option_n> 
    
        Parameter keys:
        --------------
        
        --xa-in <dir1> --xa-out <dir2> extracts CAMSS Assessments from <dir1> onto 'flattened' CSV files in <dir2>
        --ta-in <dir1> --ta-out <dir2> transforms the CSV files in <dir1> into TTL files in <dir2>
        --tc-in <dir1> --tc-out <dir2> transforms criteria from CSV files in <dir1> into TTL files in <dir2>
        --ts-in <dir1> --ts-out <dir2> transforms specifications from CSV files in <dir1> into TTL files in <dir2>
        --la-in <dir> --la-out <csv_file_pathname> piles up the basic assessment metadata from flattened CSV files in <dir1> in a <csv_file_pathname>
        --ga-in <dir> --ga-out <ttl_file_pathname> merges all graphs located in <dir> in one single TTL file
        --log <log_file_pathname> writes the output of the execution in the <log_file_pathname> specified
              
        Examples from command-line:
        --------------------------
        
        python camss.py --xa-in ./in/ass --xa-out ./out/ass/csv
        python camss.py --ta-in ./out/ass/csv --ta-out ./out/ass/ttl
        python camss.py --tc-in ./out/ass/csv --tc-out ./out/crit/ttl
        python camss.py --ts-in ./out/ass/csv --tc-out ./out/specs/ttl
        python camss.py --la-in ./out/ass/csv --la-out ./out/ass/csv/ass-list.csv
        python camss.py --ga-in ./out/ass/ttl --ga-out ./out/ass/ass-graph.ttl
        python camss.py --ga-in ./out/crit/ttl --ga-out ./out/crit/criteria-graph.ttl
        python camss.py --ga-in ./out/specs/ttl --ga-out ./out/specs/specs-graph.ttl
        python camss.py --log ./camss.log 
    
        One or more (or all) parameters above can be combined into one single line; e.g.:
    
        python camss.py --xa-in ./in/ass --xa-out ./out/ass/csv --ta-in ./out/ass/csv --ta-out=./out/ass/ttl --log ./camss.log
        
        Examples from python console, Jupyter Notebook, etc.:
        ---------------------------------------------------
        
        >>> import camss
        >>> camss.run({'--xa-in': './in/ass', '--xa-out': './out/ass/csv'})
        >>> camss.run({'--ta-in': './out/ass/csv', '--ta-out': './out/ass/ttl'})
        >>> camss.run({'--tc-in': './out/ass/csv', '--tc-out': './out/crit/ttl'})
        >>> camss.run({'--ts-in': '../out/ass/csv', '--ts-out': './out/specs/ttl'})
        >>> camss.run({'--la-in': '../out/ass/csv', '--la-out': './out/ass/csv/ass-list.csv'})
        >>> camss.run({'--ga-in': '../out/ass/ttl', '--ga-out': './out/ass/ass-graph.ttl'})
        >>> camss.run({'--ga-in': '../out/crit/ttl', '--ga-out': './out/crit/criteria-graph.ttl'})
        >>> camss.run({'--ga-in': '../out/specs/ttl', '--ga-out': './out/specs/specs-graph.ttl'})
        
        All the pipeline in one single command-line:

        >>> python camss.py --xa-in ./in/ass --xa-out ./out/ass/csv --ta-in ./out/ass/csv --ta-out ./out/ass/ttl --tc-in ./out/ass/csv --tc-out ./out/crit/ttl --ts-in ./out/ass/csv --ts-out ./out/specs/ttl --la-in ./out/ass/csv --la-out ./out/ass/ass-list.csv --ga-in ./out/ass/ttl --ga-out ./out/ass/ass-graph.ttl --log ./camss.log

        (Beware that only one -ga-* parameter can be executed at once!)
        """)


def log(message: str, nl: bool = True, level: str = 'i'):
    print(message, end='' if not nl else '\n')
    if level == 'i':
        logging.info(message)
    elif level == 'w':
        logging.warning(message)


def __extract_assessments__(xa_in: str, xa_out: str):
    index: int = -1
    # DO NOT slash() the dir, otherwise the recursive parsing takes the slash as file and iterates as many times
    # as nesting exists inside the directory.
    xa_in = xa_in.rstrip('/')
    for index, ass_file_path, filename, _ in get_files(xa_in):
        # Extracts the content of a CAMSS Assessment into a 'flattened' CSV file (see ./out dir in cfg file).
        log(f"{index}. Extracting data from '{ass_file_path}' into CSV file...", nl=False)
        # Create the out directory(ies) if they do not exist
        os.makedirs(xa_out, exist_ok=True)
        ass = Assessment(file_path=ass_file_path, filename=filename)
        o = slash(xa_out) + ass.scenario + '-' + ass.tool_version.value + '-' + filename + '.csv'
        Extractor(ass).to_csv(o)
        print("done!")
    if index == -1:
        log("The directory specified in the '--xa-in' parameters does not exist or is empty.")
        sys.exit(index)
    elif index > 0:
        log("All CSV files successfully created!")


def __get_scenario_version__(csv: _CSV) -> str:
    return csv.df.loc[0, 'scenario'] + '-' + csv.df.loc[0, 'tool_version'] + '-'


def __transform_assessments__(ta_in: str, ta_out: str):
    index: int = -1
    # DO NOT slash() the dir, otherwise the recursive parsing takes the slash as file and iterates as many times
    # as nesting exists inside the directory.
    ta_in = ta_in.rstrip('/')
    for index, csv_file_path, csv_filename, _ in get_files(ta_in):
        # Create the out directory(ies) if they do not exist
        os.makedirs(ta_out, exist_ok=True)
        csv = _CSV(file_pathname=csv_file_path, filename=csv_filename)
        # Transforms the flattened CSV data into a RDF-OWL Graph
        log(f"{index}. Transforming and saving the data from '{csv_file_path}' into a TTL file...", nl=False)
        ttl = slash(ta_out) + __get_scenario_version__(csv) + csv_filename + '.ttl'
        AssTransformer(csv).to_ttl(ttl)
        print("done!")
    if index == -1:
        log("The directory specified in the '--xa-in' parameters does not exist or is empty.", level='w')
        sys.exit(index)
    log("Done! All assessments successfully converted to OWL Turtle!")
    return


def __transform_criteria__(tc_in: str, tc_out: str):
    # Control of which types of assessment have already been processed
    processed_ass_types = {}
    # After the execution of this loop, only assessments of existing scenarios are loaded in the dictionary
    index = -1
    i = 1
    for index, ass_file_path, filename, _ in get_files(tc_in):
        os.makedirs(tc_out, exist_ok=True)
        csv = _CSV(file_pathname=ass_file_path, filename=filename)
        key = csv.scenario + str(csv.tool_version)
        # If the key does not exist, this means that this is the first time that the such a key is encountered.
        # Hence the key is used to create the entry when the exception is thrown.
        try:
            test = processed_ass_types[key]
        except:
            ttl = slash(tc_out) + csv.scenario + '-' + csv.tool_version + '-' + 'criteria.ttl'
            log_msg = f'{i}. Capturing scenario and criteria into "{ttl}" (from assessment "{ass_file_path}")...'
            log(log_msg, nl=False)
            i += 1
            processed_ass_types[key] = csv
            CritTransformer(csv).to_ttl(ttl)
            print(f'done!')
    if index == -1:
        log("The directory specified in the '--xa-in' parameters does not exist or is empty.", level='w')
        sys.exit(-1)
    log("Done! All scenarios and criteria successfully converted to OWL Turtle!")
    return


def __transform_specs__(ts_in: str, ts_out: str):
    # DO NOT slash() the dir, otherwise the recursive parsing takes the slash as file and iterates as many times
    # as nesting exists inside the directory.
    ts_in.strip('/')
    for index, ass_file_path, filename, _ in get_files(ts_in):
        os.makedirs(ts_out, exist_ok=True)
        csv = _CSV(file_pathname=ass_file_path, filename=filename)
        o = str(csv.df.loc[0, 'P1']).strip()
        o = o.replace('/', '-').replace(' ', '_').replace(':', '-').replace(';', '-').replace(',', '_').strip()
        ttl = slash(ts_out) + o + '.ttl'
        log(f'{index}. Extracting specification-related data from the Assessment {ttl} ... ', nl=False)
        SpecTransformer(csv).to_ttl(ttl)
        print("Done!")
    log("Done! All specifications successfully converted to OWL Turtle!")


def __list_ass__(la_in: str, la_out: str):
    os.makedirs(ntpath.split(la_out)[0], exist_ok=True)
    list_path_name = Assessments(la_in).to_csv(la_out)
    log(f'List of assessments successfully created (see file {list_path_name}!')
    return


def __merge_graphs__(ga_in: str, ga_out: str):
    os.makedirs(ntpath.split(ga_out)[0], exist_ok=True)
    # DO NOT slash() the dir, otherwise the recursive parsing takes the slash as file and iterates as many times
    # as nesting exists inside the directory.
    ga_in.strip('/')
    gw = GraphWorker(graph=Graph())
    gw.ttl_filename = ga_out
    for index, g_file_pathname, filename, _ in get_files(ga_in):
        log(f'{index}. Merging {g_file_pathname} into one single big Turtle TTL file...', nl=False)
        gw.merge(g_file_pathname)
        print("done!")
    log(f'Saving the big Turtle File as {ga_out}...', nl=False)
    gw.serialize()
    log(f'Done!')


def __pair_missed__(plist: [], _in: str, _out: str) -> bool:
    return (_in in plist and _out not in plist) or (_in not in plist and _out in plist)


def __pair_ok__(plist: [], _in: str, _out: str) -> bool:
    return _in in plist and _out in plist


def __pipeline__(parameters: dict):
    if not parameters or len(parameters) == 0:
        __help__()
        return

    pv = list(parameters.keys())
    if '--log' in pv:
        _log = parameters['--log']
        logging.basicConfig(filename=_log, level=logging.INFO, format='%(asctime)s %(message)s')
    # Pair check for --xa (extract assessments)
    if __pair_missed__(pv, '--xa-in', '--xa-out'):
        __help__()
    elif __pair_ok__(pv, '--xa-in', '--xa-out'):
        __extract_assessments__(parameters['--xa-in'], parameters['--xa-out'])
    # Pair check for --ta (transform assessments)
    if __pair_missed__(pv, '--ta-in', '--ta-out'):
        __help__()
    elif __pair_ok__(pv, '--ta-in', '--ta-out'):
        __transform_assessments__(parameters['--ta-in'], parameters['--ta-out'])
    # Pair check for --tc (transform criteria)
    if __pair_missed__(pv, '--tc-in', '--tc-out'):
        __help__()
    elif __pair_ok__(pv, '--tc-in', '--tc-out'):
        __transform_criteria__(parameters['--tc-in'], parameters['--tc-out'])
    # Pair check for --ts (transform specifications)
    if __pair_missed__(pv, '--ts-in', '--ts-out'):
        __help__()
    elif __pair_ok__(pv, '--ts-in', '--ts-out'):
        __transform_specs__(parameters['--ts-in'], parameters['--ts-out'])
    # Pair check for --la (list of assessments)
    if __pair_missed__(pv, '--la-in', '--la-out'):
        __help__()
    elif __pair_ok__(pv, '--la-in', '--la-out'):
        __list_ass__(parameters['--la-in'], parameters['--la-out'])
        # Pair check for --la (graph merging)
    if __pair_missed__(pv, '--ga-in', '--ga-out'):
        __help__()
    elif __pair_ok__(pv, '--ga-in', '--ga-out'):
        __merge_graphs__(parameters['--ga-in'], parameters['--ga-out'])


def __build_dirs__(argv: []) -> dict:
    parameters: dict = {}
    try:
        opts, args = getopt.getopt(argv, '', ['xa-in=', 'xa-out=',
                                              'ta-in=', 'ta-out=',
                                              'tc-in=', 'tc-out=',
                                              'ts-in=', 'ts-out=',
                                              'la-in=', 'la-out=',
                                              'ga-in=', 'ga-out=',
                                              'log='])
        # build dictionary of dirs
        for opt, arg in opts:
            parameters[opt] = arg
    except getopt.GetoptError:
        __help__()
        sys.exit(2)
    return parameters


def help():
    __help__()


def run(params: dict = None):
    """
    Use it to run the code from a python console, Jupyter Lab or Notebook, etc.
    """
    __pipeline__(params)
    return


def main(argv: []):
    """
    Runs the code from console command line
    :param argv: the sys args
    """
    __pipeline__(__build_dirs__(argv))
    return


if __name__ == '__main__':
    main(sys.argv[1:])
