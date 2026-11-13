"""One thin client per data source. Clients return parsed records and never
interpret biology; interpretation lives in bpm.analysis and bpm.evidence."""

from .kegg import KeggClient
from .ncbi import NcbiClient
from .reactome import ReactomeClient
from .stringdb import StringClient
from .uniprot import UniProtClient

__all__ = ["KeggClient", "NcbiClient", "ReactomeClient", "StringClient", "UniProtClient"]
