
# Python imports.
import logging
import os
from tablereader import TableRow, BaseTable, BaseTableReader

# Java imports.
# Python's xlrd package provides efficient, robust support for reading data
# from Excel files.  Unfortunately, it does not currently support interpreting
# Excel's cell formatting strings.  This means that there is no easy way to
# extract formatted values from an Excel worksheet in a way that will (or is
# likely to) match what Excel displays.  Apache POI, on the other hand, does
# provide this functionality, so we use it instead.
from java.io import File
from org.apache.poi.ss.usermodel import WorkbookFactory, CellType
from org.apache.poi.ss.usermodel import DataFormatter, FormulaEvaluator

class _ExcelTable(BaseTable):
    """
    Represents a single table (i.e., sheet) in a Microsoft Excel spreadsheet
    file.  _ExcelTable assumes that the first row of the sheet contains the
    column names.  Each subsequent row is returned as a TableRow object; thus,
    column names are not case sensitive.
    """
    # Define the supported spreadsheet cell data types.
    SUPPORTED_CELL_TYPES = (CellType.BLANK, CellType.BOOLEAN, CellType.FORMULA,
        CellType.NUMERIC, CellType.STRING)

    def __init__(self, excelsheet, filename, required_cols=[], optional_cols=[], default_vals={}):
        BaseTable.__init__(self, excelsheet.getSheetName(), required_cols, optional_cols, default_vals)

        self.sheet = excelsheet
        self.filename = filename

        # Get a DataFormtater and FormulaEvaluator so that we can extract
        # strings from cells that match the output produced by Excel's UI.
        self.df = DataFormatter(False)
        self.fe = self.sheet.getWorkbook().getCreationHelper().createFormulaEvaluator()

        self.numrows = self.sheet.getLastRowNum() + 1
        #print 'RAW ROW COUNT:', self.numrows
        self.rowcnt = 0

        # Get the column names from the sheet and infer the number of used
        # columns.  The first empty cell encountered in the first row of the
        # sheet is considered to mark the end of the used columns.
        self.colnames = []
        if self.numrows > 0:
            row = self.sheet.getRow(0)
            if row != None:
                for colnum in range(row.getLastCellNum()):
                    cellval = self._cellStrValue(row.getCell(colnum))
                    if cellval == '':
                        break
                    self.colnames.append(cellval)
            self.rowcnt = 1
        self.numcols = len(self.colnames)
        #print 'USED COLUMN COUNT:', self.numcols

        if self.numcols == 0:
            raise RuntimeError('The input Excel spreadsheet "' + self.name
                    + '" in the file "' + self.filename
                    + '" appears to be empty.')

        # Trim the column names and make sure they are unique.
        nameset = set()
        for colnum in range(len(self.colnames)):
            self.colnames[colnum] = self.colnames[colnum].strip().lower()
            if self.colnames[colnum] in nameset:
                raise RuntimeError('The column name "' + self.colnames[colnum]
                    + '" is used more than once in the input Excel spreadsheet "'
                    + self.name + '" in the file "' + self.filename
                    + '".  All column names must be unique.')
            else:
                nameset.add(self.colnames[colnum])

    def _cellStrValue(self, cell):
        """
        Returns the value of an Excel spreadsheet cell as a string.
        """
        ctype = cell.getCellTypeEnum()

        if ctype in self.SUPPORTED_CELL_TYPES:
            return self.df.formatCellValue(cell, self.fe)
        elif ctype == CellType.ERROR:
            raise RuntimeError('Error detected in row ' + str(self.rowcnt)
                    + ' of the input Excel spreadsheet "' + self.name
                    + '" in the file "' + self.filename + '".')
        else:
            raise RuntimeError('Unrecognized cell data type in row '
                    + str(self.rowcnt) + ' of the input Excel spreadsheet "'
                    + self.name + '" in the file "' + self.filename + '".')

    def next(self):
        """
        Allows iteration through each row of the Excel spreadsheet table. Empty
        rows are ignored.
        """
        # Find the next non-empty row.  After the loop, self.rowcnt will be at
        # the next non-empty row, assuming counting starts at 1 (if the search
        # succeeded).
        emptyrow = True
        nextrow = None
        while (self.rowcnt < self.numrows) and emptyrow:
            nextrow = self.sheet.getRow(self.rowcnt)
            if nextrow != None:
                for colnum in range(self.numcols):
                    if self._cellStrValue(nextrow.getCell(colnum)) != '':
                        emptyrow = False
                        break
            self.rowcnt += 1

        if emptyrow:
            raise StopIteration()

        trow = TableRow(
            self.rowcnt, self.filename,
            self.required_cols, self.optional_cols, self.defaultvals
        )
        for colnum in range(self.numcols):
            cell = nextrow.getCell(colnum)
            # Uncomment the following line to print the Excel value type for
            # each data cell.
            #print cell.getCellTypeEnum()
            trow[self.colnames[colnum]] = self._cellStrValue(cell)

        return trow


class ExcelTableReader(BaseTableReader):
    """
    Reads tables (i.e., sheets) from a Microsoft Excel spreadsheet file.
    """
    def __init__(self, filepath):
        BaseTableReader.__init__(self)

        self.filename = filepath
        self.wbook = WorkbookFactory.create(File(self.filename))

        self.numtables = self.wbook.getNumberOfSheets()

    def getTableByIndex(self, index):
        if (index < 0) or (index >= self.numtables):
            raise KeyError('Invalid table index:' + str(index)
                    + '.  No matching sheet could be found in the file "'
                    + self.filename + '".')

        return _ExcelTable(self.wbook.getSheetAt(index), self.filename)

    def getTableByName(self, tablename):
        sheet = self.wbook.getSheet(tablename)
        if sheet == None:
            raise KeyError('Invalid table name: "' + str(tablename)
                    + '".  No matching sheet could be found in the file "'
                    + self.filename + '".')

        table = _ExcelTable(sheet, self.filename)

        return table

