
#
# Manages the process of building an ontology from a base ontology file and
# zero or more input terms files.
#

# Python imports.
import os
import glob
from tablereaderfactory import TableReaderFactory
from owlontologybuilder import OWLOntologyBuilder, TermDescriptionError
from ontobuilder import TRUE_STRS
from buildtarget import BuildTarget
from imports_buildtarget import ImportsBuildTarget
from inferred_axiom_adder import InferredAxiomAdder

# Java imports.


# Required columns in terms files.
REQUIRED_COLS = ('Type', 'ID')

# Optional columns in terms files.
OPTIONAL_COLS = (
    'Comments', 'Parent', 'Subclass of', 'Equivalent to', 'Disjoint with',
    'Inverse', 'Characteristics', 'Ignore'
)
        
class OntoBuildTarget(BuildTarget):
    def __init__(
            self, config, mergeimports=False, prereason=False,
            check_consistency=False, expanddefs=True
        ):
        """
        config: An OntoConfig instance.
        mergeimports: Whether to merge imported terms into the main ontology.
        prereason: Whether to add inferred axioms to the compiled ontology.
        check_consistency: Whether to use a reasoner to check if the compiled
            ontology is logically consistent.
        expanddefs: Whether to add IDs to term references in definitions.
        """
        BuildTarget.__init__(self)

        self.config = config
        self.mergeimports = mergeimports
        self.prereason = prereason
        self.check_consistency = check_consistency
        self.expanddefs = expanddefs

        # Set the imports modules as a dependency, regardless of whether we're
        # using in-source or out-of-source builds.  Either way, it is probably
        # best for end users to make sure imports modules remain updated.  Of
        # course, for out-of-source builds, it is up to the user to make sure
        # the imports modules get copied to their destination location.
        self.ibt = ImportsBuildTarget(self.config)
        self.addDependency(self.ibt)

    def _getExpandedTermsFilesList(self):
        """
        Prepares the list of terms files by expanding any paths with
        shell-style wildcards.  Verifies that each path string resolves to one
        or more valid paths, and eliminates any duplicate paths.
        """
        pathsset = set()

        # Attempt to expand each terms path string and eliminate any duplicate
        # paths by building a set of path strings.
        for fpath in self.config.getTermsFilePaths():
            flist = glob.glob(fpath)
            if len(flist) == 0:
                raise RuntimeError(
                    'The source terms/entities file(s) could not be found: {0}.'.format(fpath)
                )
            for filename in flist:
                pathsset.add(filename)

        return list(pathsset)

    def _retrieveAndCheckFilePaths(self):
        """
        Verifies that all files and directories needed for the build exist.
        Once file paths are retrieved from the OntoConfig instance, expanded,
        and verified, they are cached as instance attributes for later use in
        the build process.
        """
        # Verify that the base ontology file exists.
        fpath = self.config.getBaseOntologyPath()
        if not(os.path.isfile(fpath)):
            raise RuntimeError(
                'The base ontology file could not be found: {0}.'.format(fpath)
            )
        self.base_ont_path = fpath

        # Verify that the terms files exist and are of correct type.  The
        # method _expandTermsFilesList() ensures that all paths are valid in
        # the list it returns.
        pathslist = self._getExpandedTermsFilesList()
        for fpath in pathslist:
            if not(os.path.isfile(fpath)):
                raise RuntimeError(
                    'The source terms/entities path "{0}" exists, but is not a valid file.'.format(fpath)
                )
        self.termsfile_paths = pathslist

        # Verify that the build directory exists.
        destdir = os.path.dirname(self._getOutputFilePath())
        if not(os.path.isdir(destdir)):
            raise RuntimeError(
                'The destination directory for the ontology does not exist: {0}.'.format(destdir)
            )

    def _getOutputFilePath(self):
        """
        Returns the path of the compiled ontology file.
        """
        if self.config.getDoInSourceBuilds():
            destpath = self.config.getOntologyFilePath()
        else:
            ontfilename = os.path.basename(self.config.getOntologyFilePath())
            destpath = os.path.join(self.config.getBuildDir(), ontfilename)

        # If we are merging the import modules into the ontology (rather than
        # using import statements), modify the file name accordingly.
        if self.mergeimports:
            parts = os.path.splitext(destpath)
            destpath = parts[0] + '-merged' + parts[1]

        # If we are adding inferred axioms to the ontology, modify the file
        # name accordingly.
        if self.prereason:
            parts = os.path.splitext(destpath)
            destpath = parts[0] + '-reasoned' + parts[1]

        return destpath

    def getBuildNotRequiredMsg(self):
        return 'The compiled ontology is already up to date.'

    def _isBuildRequired(self):
        """
        Checks if the compiled ontology already exists, and if so, whether file
        modification times indicate that the compiled ontology is already up to
        date.  Returns True if the compiled ontology needs to be updated.
        """
        foutpath = self._getOutputFilePath()

        if os.path.isfile(foutpath):
            mtime = os.path.getmtime(foutpath)

            # If the configuration file is newer than the compiled ontology, a
            # new build might be needed if new terms files have been added or
            # other ontology-related changes were made.
            if mtime < os.path.getmtime(self.config.getConfigFilePath()):
                return True

            # Check the modification time of the base ontology.
            if mtime < os.path.getmtime(self.config.getBaseOntologyPath()):
                return True

            # Check the modification time of each terms file.
            for termsfile in self.config.getTermsFilePaths():
                if mtime < os.path.getmtime(termsfile):
                    return True

            return False
        else:
            return True

    def _run(self):
        """
        Runs the build process and produces a compiled OWL ontology file.
        """
        if not(self._isBuildRequired()):
            return

        # Get the imports modules IRIs from the imports build target.
        importsIRIs = self.ibt.getImportsIRIs()

        self._retrieveAndCheckFilePaths()

        ontbuilder = OWLOntologyBuilder(self.base_ont_path)
        # Add all import modules to the ontology.
        if self.mergeimports:
            # Merge the axioms from each import module directly into this
            # ontology (that is, do not use import statements).
            for importIRI in importsIRIs:
                ontbuilder.getOntology().mergeOntology(importIRI)
        else:
            # Add an import declaration for each import module.
            for importIRI in importsIRIs:
                ontbuilder.getOntology().addImport(importIRI, True)

        # Process each source file.  In this step, entities and label
        # annotations are defined, but processing of all other axioms (e.g.,
        # text definitions, comments, equivalency axioms, subclass of axioms,
        # etc.) is deferred until after all input files have been read.  This
        # allows forward referencing of labels and term IRIs and means that
        # entity descriptions and source files can be processed in any
        # arbitrary order.
        for termsfile in self.termsfile_paths:
            with TableReaderFactory(termsfile) as reader:
                print 'Parsing ' + termsfile + '...'
                for table in reader:
                    table.setRequiredColumns(REQUIRED_COLS)
                    table.setOptionalColumns(OPTIONAL_COLS)
        
                    for t_row in table:
                        if not(t_row['Ignore'].lower() in TRUE_STRS):
                            # Collapse all spaces in the "Type" string so that,
                            # e.g., "DataProperty" and "Data Property" will
                            # both work as expected.
                            typestr = t_row['Type'].lower().replace(' ', '')
            
                            if typestr == 'class':
                                ontbuilder.addClass(t_row)
                            elif typestr == 'dataproperty':
                                ontbuilder.addDataProperty(t_row)
                            elif typestr == 'objectproperty':
                                ontbuilder.addObjectProperty(t_row)
                            elif typestr == 'annotationproperty':
                                ontbuilder.addAnnotationProperty(t_row)
                            elif typestr == '':
                                raise TermDescriptionError(
                                    'The entity type (e.g., "class", "data property") was not specified.',
                                    t_row
                                )
                            else:
                                raise TermDescriptionError(
                                    'The entity type "' + t_row['Type']
                                    + '" is not supported.', t_row
                                )

        # Define all deferred axioms from the source entity descriptions.
        print 'Defining all remaining entity axioms...'
        ontbuilder.processDeferredEntityAxioms(self.expanddefs)

        if self.prereason or self.check_consistency:
            print 'Checking whether the ontology is logically consistent...'

        if self.prereason:
            print 'Running reasoner and adding inferred axioms...'
            ontology = ontbuilder.getOntology()
            inf_types = self.config.getInferenceTypeStrs()
            annotate_inferred = self.config.getAnnotateInferred()
            iaa = InferredAxiomAdder(ontology, self.config.getReasonerStr())
            iaa.addInferredAxioms(inf_types, annotate_inferred)

        # Set the ontology ID, if an ontology IRI was provided.
        ontIRI = self.config.getOntologyIRI()
        if ontIRI != '':
            ontbuilder.getOntology().setOntologyID(ontIRI)

        # Write the ontology to the output file.
        fileoutpath = self._getOutputFilePath()
        print 'Writing compiled ontology to ' + fileoutpath + '...'
        ontbuilder.getOntology().saveOntology(fileoutpath)
