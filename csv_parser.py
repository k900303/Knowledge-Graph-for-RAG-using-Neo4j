"""
CSV Parser for Company Master Data
Extracts structured data from company_master CSV for Neo4j ingestion
"""

import csv
from typing import List, Dict, Set
from dataclasses import dataclass, field


@dataclass
class Company:
    """Represents a company entity"""
    company_id: str
    company_name: str
    country_code: str
    country: str
    region_id: str
    region: str
    sector_id: str
    sector_name: str
    industry_id: str
    industry_name: str
    exchange: str
    exchange_symbol: str
    market_cap: float
    base_currency: str
    one_week_change: float
    this_month_change: float
    this_quarter_change: float
    status: str
    isin: str = ""
    va_ticker: str = ""


@dataclass
class Parameter:
    """Represents a financial/operational parameter - optimized with 6 essential fields only"""
    param_id: str
    parameter_name: str
    parameter_type: str  # opssd, sd, cd, etc.
    cid: str  # company_id
    unit: str
    isprimary: int


@dataclass
class PeriodResult:
    """Represents a period-based result value for a parameter - optimized with 11 essential fields only"""
    id: str  # unique identifier
    cid: str  # company_id
    pid: str  # parameter_id
    period: str  # period like "3QFY-2024" (mapped from 'p')
    actual_period: str  # actual period value (mapped from 'ap')
    value: float  # the actual value (mapped from 'v')
    currency: str  # currency code (mapped from 'ciso')
    unit: int  # unit type (mapped from 'u')
    data_type: str  # A=Actual, E=Estimated, etc. (mapped from 'dt')
    yoy_growth: float = 0.0  # year-over-year growth (mapped from 'yoypc')
    seq_growth: float = 0.0  # sequential growth (mapped from 'seqpc')


class CSVParser:
    """Parser for company master CSV file"""
    
    def __init__(self, csv_file_path: str):
        self.csv_file_path = csv_file_path
        self.companies: List[Company] = []
        self.countries: Set[str] = set()
        self.regions: Set[str] = set()
        self.sectors: Dict[str, str] = {}  # {sector_id: sector_name}
        self.industries: Dict[str, str] = {}  # {industry_id: industry_name}
        self.exchanges: Set[str] = set()
    
    def parse(self) -> List[Company]:
        """Parse the CSV file and extract all entities"""
        print(f"Parsing CSV file: {self.csv_file_path}")
        
        with open(self.csv_file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row_num, row in enumerate(reader, start=2):  # Start at 2 (row 1 is header)
                try:
                    # Extract company data
                    company = self._parse_company(row)
                    
                    if company and company.status == 'Active':  # Only active companies
                        self.companies.append(company)
                        
                        # Collect unique entities
                        self.countries.add(company.country_code)
                        self.regions.add(company.region)
                        self.sectors[company.sector_id] = company.sector_name
                        self.industries[company.industry_id] = company.industry_name
                        if company.exchange:
                            self.exchanges.add(company.exchange)
                        
                except Exception as e:
                    print(f"Error parsing row {row_num}: {e}")
                    continue
        
        print(f"Parsed {len(self.companies)} companies")
        print(f"Found {len(self.countries)} countries, {len(self.regions)} regions")
        print(f"Found {len(self.sectors)} sectors, {len(self.industries)} industries")
        
        return self.companies
    
    def _parse_company(self, row: Dict) -> Company:
        """Parse a single row into a Company object"""
        # Handle numeric conversions with defaults
        market_cap = self._safe_float(row.get('market_cap') or row.get('mcap', '0'))
        one_week = self._safe_float(row.get('one_week_change', '0'))
        this_month = self._safe_float(row.get('this_month_change', '0'))
        this_quarter = self._safe_float(row.get('this_quarter_change', '0'))
        
        return Company(
            company_id=row.get('company_id', ''),
            company_name=row.get('company_name', '').strip(),
            country_code=row.get('country_code', ''),
            country=row.get('country', '').strip(),
            region_id=row.get('region_id', ''),
            region=row.get('region', '').strip(),
            sector_id=row.get('sector_id', ''),
            sector_name=row.get('sector_name', '').strip(),
            industry_id=row.get('industry_id', ''),
            industry_name=row.get('industry_name', '').strip(),
            exchange=row.get('exchange', '').strip(),
            exchange_symbol=row.get('exchange_symbol', '').strip(),
            market_cap=market_cap,
            base_currency=row.get('base_currency', '').strip(),
            one_week_change=one_week,
            this_month_change=this_month,
            this_quarter_change=this_quarter,
            status=row.get('status', '').strip(),
            isin=row.get('isin', '').strip(),
            va_ticker=row.get('va_ticker', '').strip()
        )
    
    def _safe_float(self, value: str, default: float = 0.0) -> float:
        """Safely convert string to float"""
        try:
            if not value or value.strip() == '':
                return default
            return float(value)
        except (ValueError, TypeError):
            return default
    
    def get_companies(self) -> List[Company]:
        """Get all parsed companies"""
        return self.companies
    
    def get_unique_countries(self) -> List[str]:
        """Get unique country codes"""
        return sorted(list(self.countries))
    
    def get_unique_regions(self) -> List[str]:
        """Get unique regions"""
        return sorted(list(self.regions))
    
    def get_sectors(self) -> Dict[str, str]:
        """Get sector mapping"""
        return self.sectors
    
    def get_industries(self) -> Dict[str, str]:
        """Get industry mapping"""
        return self.industries
    
    def get_exchanges(self) -> List[str]:
        """Get unique exchanges"""
        return sorted(list(self.exchanges))


class ParameterParser:
    """Parser for parameter CSV file"""
    
    def __init__(self, csv_file_path: str):
        self.csv_file_path = csv_file_path
        self.parameters: List[Parameter] = []
    
    def parse(self, target_cid: str = "18315", allowed_types: List[str] = ["opssd", "sd"]) -> List[Parameter]:
        """Parse parameter CSV file with filtering"""
        print(f"Parsing parameter CSV file: {self.csv_file_path}")
        print(f"Filtering for cid={target_cid}, types={allowed_types}")
        
        with open(self.csv_file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row_num, row in enumerate(reader, start=2):
                try:
                    # Check filtering criteria
                    cid = row.get('cid', '').strip()
                    param_type = row.get('parameter_type', '').strip()
                    
                    if cid == target_cid and param_type in allowed_types:
                        parameter = self._parse_parameter(row)
                        if parameter:
                            self.parameters.append(parameter)
                
                except Exception as e:
                    print(f"Error parsing parameter row {row_num}: {e}")
                    continue
        
        print(f"Parsed {len(self.parameters)} parameters")
        return self.parameters
    
    def _parse_parameter(self, row: Dict) -> Parameter:
        """Parse a single row into a Parameter object - optimized for 6 essential fields only"""
        return Parameter(
            param_id=row.get('param_id', '').strip(),
            parameter_name=row.get('parameter_name', '').strip(),
            parameter_type=row.get('parameter_type', '').strip(),
            cid=row.get('cid', '').strip(),
            unit=row.get('unit', '').strip(),
            isprimary=int(row.get('isprimary', '0'))
        )
    
    def get_parameters(self) -> List[Parameter]:
        """Get all parsed parameters"""
        return self.parameters


class ResultsParser:
    """Parser for results CSV file"""
    
    def __init__(self, csv_file_path: str):
        self.csv_file_path = csv_file_path
        self.results: List[PeriodResult] = []
    
    def parse(self, target_cid: str = "18315") -> List[PeriodResult]:
        """Parse results CSV file with filtering"""
        print(f"Parsing results CSV file: {self.csv_file_path}")
        print(f"Filtering for cid={target_cid}")
        
        with open(self.csv_file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row_num, row in enumerate(reader, start=2):
                try:
                    # Check filtering criteria
                    cid = row.get('cid', '').strip()
                    
                    if cid == target_cid:
                        result = self._parse_result(row)
                        if result:
                            self.results.append(result)
                
                except Exception as e:
                    print(f"Error parsing result row {row_num}: {e}")
                    continue
        
        print(f"Parsed {len(self.results)} period results")
        return self.results
    
    def _parse_result(self, row: Dict) -> PeriodResult:
        """Parse a single row into a PeriodResult object - optimized for 11 essential fields only"""
        # Extract pid from id field (format: cid_pid_sid_period)
        id_field = row.get('id', '').strip()
        pid = ""
        if '_' in id_field:
            parts = id_field.split('_')
            if len(parts) >= 2:
                pid = parts[1]  # Second part is pid
        
        return PeriodResult(
            id=id_field,
            cid=row.get('cid', '').strip(),
            pid=pid,
            period=row.get('p', '').strip(),
            actual_period=row.get('ap', '').strip(),
            value=self._safe_float(row.get('v', '0')),
            currency=row.get('ciso', '').strip(),
            unit=self._safe_int(row.get('u', '0')),
            data_type=row.get('dt', '').strip(),
            yoy_growth=self._safe_float(row.get('yoypc', '0')),
            seq_growth=self._safe_float(row.get('seqpc', '0'))
        )
    
    def _safe_int(self, value: str, default: int = 0) -> int:
        """Safely convert string to int"""
        try:
            if not value or value.strip() == '':
                return default
            return int(value)
        except (ValueError, TypeError):
            return default
    
    def _safe_float(self, value: str, default: float = 0.0) -> float:
        """Safely convert string to float"""
        try:
            if not value or value.strip() == '':
                return default
            return float(value)
        except (ValueError, TypeError):
            return default
    
    def get_results(self) -> List[PeriodResult]:
        """Get all parsed results"""
        return self.results


def parse_company_csv(csv_file_path: str) -> CSVParser:
    """
    Parse company master CSV file
    
    Args:
        csv_file_path: Path to the company master CSV file
    
    Returns:
        CSVParser object with parsed data
    """
    parser = CSVParser(csv_file_path)
    parser.parse()
    return parser


def parse_parameter_csv(csv_file_path: str, target_cid: str = "18315", 
                       allowed_types: List[str] = ["opssd", "sd"]) -> ParameterParser:
    """
    Parse parameter CSV file with filtering
    
    Args:
        csv_file_path: Path to the parameter CSV file
        target_cid: Company ID to filter for
        allowed_types: List of parameter types to include
    
    Returns:
        ParameterParser object with parsed data
    """
    parser = ParameterParser(csv_file_path)
    parser.parse(target_cid, allowed_types)
    return parser


def parse_results_csv(csv_file_path: str, target_cid: str = "18315") -> ResultsParser:
    """
    Parse results CSV file with filtering
    
    Args:
        csv_file_path: Path to the results CSV file
        target_cid: Company ID to filter for
    
    Returns:
        ResultsParser object with parsed data
    """
    parser = ResultsParser(csv_file_path)
    parser.parse(target_cid)
    return parser


if __name__ == '__main__':
    # Test the parser
    csv_path = 'data/PEERS_PROD_RAW_CSV_DATA/company_master_csv.txt'
    parser = parse_company_csv(csv_path)
    
    print(f"\nTotal companies: {len(parser.get_companies())}")
    print(f"\nSample companies:")
    for i, company in enumerate(parser.get_companies()[:5]):
        print(f"\n{i+1}. {company.company_name}")
        print(f"   ID: {company.company_id}")
        print(f"   Country: {company.country} ({company.country_code})")
        print(f"   Sector: {company.sector_name}")
        print(f"   Industry: {company.industry_name}")
        print(f"   Market Cap: {company.market_cap:,.0f} {company.base_currency}")
        print(f"   Exchange: {company.exchange}")

