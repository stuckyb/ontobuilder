#
# Provides a convenience Ontology class that implements a high-level interface
# for interacting with an OWL ontology.
#

# Python imports.
from labelmap import LabelMap
from obohelper import isOboID, oboIDToIRI
from ontology_entities import _OntologyClass, _OntologyDataProperty
from ontology_entities import _OntologyObjectProperty, _OntologyAnnotationProperty
from rfc3987 import rfc3987

# Java imports.
from java.io import File, FileOutputStream
from java.util import HashSet
from java.lang import UnsupportedOperationException
from org.semanticweb.owlapi.apibinding import OWLManager
from org.semanticweb.owlapi.model import IRI, OWLOntologyID
from org.semanticweb.owlapi.model import AddAxiom, AddImport, RemoveImport
from org.semanticweb.owlapi.model import SetOntologyID, AxiomType, OWLOntology
from org.semanticweb.owlapi.model import AddOntologyAnnotation
from org.semanticweb.owlapi.model import OWLRuntimeException
from org.semanticweb.owlapi.formats import RDFXMLDocumentFormat
from org.semanticweb.elk.owlapi import ElkReasonerFactory
from org.semanticweb import HermiT
from uk.ac.manchester.cs.owlapi.modularity import SyntacticLocalityModuleExtractor
from uk.ac.manchester.cs.owlapi.modularity import ModuleType
from com.google.common.base import Optional
from org.semanticweb.owlapi.io import OWLOntologyCreationIOException
from org.semanticweb.owlapi.model import OWLOntologyFactoryNotFoundException
from org.semanticweb.owlapi.model.parameters import Imports as ImportsEnum
from org.semanticweb.owlapi.reasoner import InferenceType
from org.semanticweb.owlapi.util import InferredSubClassAxiomGenerator
from org.semanticweb.owlapi.util import InferredEquivalentClassAxiomGenerator
from org.semanticweb.owlapi.util import InferredSubDataPropertyAxiomGenerator
from org.semanticweb.owlapi.util import InferredSubObjectPropertyAxiomGenerator
from org.semanticweb.owlapi.util import InferredClassAssertionAxiomGenerator
from org.semanticweb.owlapi.util import InferredDisjointClassesAxiomGenerator
from org.semanticweb.owlapi.util import InferredOntologyGenerator


class Ontology:
    """
    Provides a high-level interface to the OWL API's ontology object system.
    Conceptually, instances of this class represent a single OWL ontology.
    """
    # The IRI for the "dc:source" annotation property.
    SOURCE_PROP_IRI = IRI.create('http://purl.org/dc/elements/1.1/source')

    # The IRI for inferred axiom annotation.
    INFERRED_ANNOT_IRI = IRI.create(
        'http://www.geneontology.org/formats/oboInOwl#is_inferred'
    )

    def __init__(self, ontology_source):
        """
        Initialize this Ontology instance.  The argument "ontology_source"
        should either be a path to an OWL ontology file on the local file
        system or an instance of an OWL API OWLOntology object.
        """
        if isinstance(ontology_source, basestring): 
            # Load the ontology from the source file.
            self.ontman = OWLManager.createOWLOntologyManager()
            ontfile = File(ontology_source)
            self.ontology = self.ontman.loadOntologyFromOntologyDocument(ontfile)
        elif isinstance(ontology_source, OWLOntology):
            self.ontology = ontology_source
            self.ontman = self.ontology.getOWLOntologyManager()
        else:
            raise RuntimeError('Unrecognized type for initializing an Ontology object: '
                + str(ontology_source))

        self.labelmap = LabelMap(self.ontology)

        # Create an OWL data factory, which is required for creating new OWL
        # entities and looking up existing entities.
        self.df = OWLManager.getOWLDataFactory()

    def getOWLOntology(self):
        """
        Returns the OWL API ontology object contained by this Ontology object.
        """
        return self.ontology

    def getOntologyManager(self):
        """
        Returns the OWL API ontology manager object contained by this Ontology.
        """
        return self.ontman

    def labelToIRI(self, labeltxt):
        """
        Given a class label, returns the associated class IRI.
        """
        try:
            cIRI = self.labelmap.lookupIRI(labeltxt)
        except KeyError:
            raise RuntimeError('The class label, "' + labeltxt
                + '", could not be matched to a term IRI.')

        return cIRI

    def expandIRI(self, iri):
        """
        Expands an IRI string into a full IRI and returns a corresponding OWL
        API IRI object.  Also accepts OWL API IRI objects, in which case they
        are returned unaltered.  IRI strings can be either full IRIs, prefix
        IRIs (i.e. curies, such as "owl:Thing"), or relative IRIs (e.g.,
        "term_name").  If the IRI string is a prefix IRI or relative IRI, it
        will be expanded using the prefixes or base defined in the ontology.
        If the string is not a prefix IRI or relative IRI, then it is assumed
        to be a full IRI.

        iri: The IRI to expand.  Can be either a string or an OWL API IRI
            object.  In the latter case, iri is returned as is.
        """
        prefix_df = self.ontman.getOntologyFormat(self.ontology).asPrefixOWLOntologyFormat()

        if isinstance(iri, basestring):
            # Verify that we have a valid IRI string.
            if rfc3987.match(iri, rule='IRI_reference') == None:
                raise RuntimeError('Invalid IRI string: "' + iri + '".')

            try:
                # If iri is not a prefix IRI, the OWL API will throw an
                # OWLRuntimeException.
                fullIRI = prefix_df.getIRI(iri)
            except OWLRuntimeException:
                fullIRI = IRI.create(iri)
        elif isinstance(iri, IRI):
            fullIRI = iri
        else:
            raise RuntimeError('Unsupported type for conversion to IRI.')

        return fullIRI

    def expandIdentifier(self, id_obj):
        """
        Converts an object representing an identifier into a fully expanded
        IRI.  The argument id_obj can be either an OWL API IRI object or a
        string containing: a prefix IRI (i.e., a curie, such as "owl:Thing"), a
        relative IRI, a full IRI, or an OBO ID (e.g., a string of the form
        "PO:0000003").  Returns an OWL API IRI object.
        """
        if isinstance(id_obj, basestring):
            if isOboID(id_obj):
                IRIobj = oboIDToIRI(id_obj)
            else:
                IRIobj = self.expandIRI(id_obj)
        elif isinstance(id_obj, IRI):
            IRIobj = id_obj
        else:
            raise RuntimeError('Unsupported type for conversion to IRI.')

        return IRIobj

    def getExistingClass(self, class_id):
        """
        Searches for an existing class in the ontology.  If the class is
        declared either directly in the ontology or is declared in its
        transitive imports closure, an _OntologyEntity object representing the
        class is returned.  Otherwise, None is returned.

        class_id: The identifier of the class to search for.  Can be either an
            OWL API IRI object or a string containing: a prefix IRI (i.e., a
            curie, such as "owl:Thing"), a relative IRI, a full IRI, or an OBO
            ID (e.g., a string of the form "PO:0000003").
        """
        classIRI = self.expandIdentifier(class_id)

        classobj = self.df.getOWLClass(classIRI)

        ontset = self.ontology.getImportsClosure()
        for ont in ontset:
            if ont.getDeclarationAxioms(classobj).size() > 0:
                return _OntologyClass(classIRI, classobj, self)

        return None

    def getExistingDataProperty(self, prop_id):
        """
        Searches for an existing data property in the ontology.  If the
        property is declared either directly in the ontology or is declared in
        its transitive imports closure, an _OntologyDataProperty object
        representing the property is returned.  Otherwise, None is returned.

        prop_id: The identifier of the property to search for.  Can be either
            an OWL API IRI object or a string containing: a prefix IRI (i.e., a
            curie, such as "owl:Thing"), a full IRI, a relative IRI, or an OBO
            ID (e.g., a string of the form "PO:0000003").
        """
        propIRI = self.expandIdentifier(prop_id)

        propobj = self.df.getOWLDataProperty(propIRI)

        ontset = self.ontology.getImportsClosure()
        for ont in ontset:
            if ont.getDeclarationAxioms(propobj).size() > 0:
                return _OntologyDataProperty(propIRI, propobj, self)

        return None

    def getExistingObjectProperty(self, prop_id):
        """
        Searches for an existing object property in the ontology.  If the
        property is declared either directly in the ontology or is declared in
        its transitive imports closure, an _OntologyObjectProperty object
        representing the property is returned.  Otherwise, None is returned.

        prop_id: The identifier of the property to search for.  Can be either
            an OWL API IRI object or a string containing: a prefix IRI (i.e., a
            curie, such as "owl:Thing"), a full IRI, a relative IRI, or an OBO
            ID (e.g., a string of the form "PO:0000003").
        """
        propIRI = self.expandIdentifier(prop_id)

        propobj = self.df.getOWLObjectProperty(propIRI)

        ontset = self.ontology.getImportsClosure()
        for ont in ontset:
            if ont.getDeclarationAxioms(propobj).size() > 0:
                return _OntologyObjectProperty(propIRI, propobj, self)

        return None

    def getExistingAnnotationProperty(self, prop_id):
        """
        Searches for an existing annotation property in the ontology.  If the
        property is declared either directly in the ontology or is declared in
        its transitive imports closure, an _OntologyAnnotationProperty object
        representing the property is returned.  Otherwise, None is returned.

        prop_id: The identifier of the property to search for.  Can be either
            an OWL API IRI object or a string containing: a prefix IRI (i.e., a
            curie, such as "owl:Thing"), a full IRI, a relative IRI, or an OBO
            ID (e.g., a string of the form "PO:0000003").
        """
        propIRI = self.expandIdentifier(prop_id)

        propobj = self.df.getOWLAnnotationProperty(propIRI)

        ontset = self.ontology.getImportsClosure()
        for ont in ontset:
            if ont.getDeclarationAxioms(propobj).size() > 0:
                return _OntologyAnnotationProperty(propIRI, propobj, self)

        return None

    def getExistingProperty(self, prop_id):
        """
        Searches for an existing property in the ontology.  If the property is
        declared either directly in the ontology or is declared in its
        transitive imports closure, an _OntologyEntity object representing the
        property is returned.  Otherwise, None is returned.  Object properties,
        data properties, and annotation properties are all considered; ontology
        properties are not.

        prop_id: The identifier of the property to search for.  Can be either
            an OWL API IRI object or a string containing: a prefix IRI (i.e., a
            curie, such as "owl:Thing"), a full IRI, a relative IRI, or an OBO
            ID (e.g., a string of the form "PO:0000003").
        """
        propIRI = self.expandIdentifier(prop_id)

        prop = self.getExistingObjectProperty(propIRI)
        if prop == None:
            prop = self.getExistingAnnotationProperty(propIRI)
        if prop == None:
            prop = self.getExistingDataProperty(propIRI)

        # If no matching data property was found, prop == None.
        return prop

    def getExistingEntity(self, ent_id):
        """
        Searches for an entity in the ontology using an identifier.  The entity
        is assumed to be either a class, object property, data property, or
        annotation property.  Both the main ontology and its imports closure
        are searched for the target entity.  If the entity is found, an
        _OntologyEntity object representing the entity is returned.  Otherwise,
        None is returned.
        
        ent_id: The identifier of the entity.  Can be either an OWL API IRI
            object or a string containing: a prefix IRI (i.e., a curie, such as
            "owl:Thing"), a full IRI, a relative IRI, or an OBO ID (e.g., a
            string of the form "PO:0000003").
        """
        eIRI = self.expandIdentifier(ent_id)

        entity = self.getExistingClass(eIRI)
        if entity == None:
            entity = self.getExistingProperty(eIRI)

        # If no matching data property was found, entity == None.
        return entity

    def getExistingIndividual(self, indv_id):
        """
        Searches for an existing individual in the ontology.  If the individual
        is declared either directly in the ontology or is declared in its
        transitive imports closure, an OWL API object representing the
        individual is returned.  Otherwise, None is returned.

        indv_id: The identifier of the individual to search for.  Can be either
            an OWL API IRI object or a string containing: a prefix IRI (i.e., a
            curie, such as "owl:Thing"), a full IRI, a relative IRI, or an OBO
            ID (e.g., a string of the form "PO:0000003").
        """
        indvIRI = self.expandIdentifier(indv_id)

        indvobj = self.df.getOWLNamedIndividual(indvIRI)

        ontset = self.ontology.getImportsClosure()
        for ont in ontset:
            if ont.getDeclarationAxioms(indvobj).size() > 0:
                return indvobj

        return None

    def createNewClass(self, class_id):
        """
        Creates a new OWL class, adds it to the ontology, and returns an
        associated _OntologyClass object.

        class_id: The identifier for the new class.  Can be either an OWL API
            IRI object or a string containing: a prefix IRI (i.e., a curie,
            such as "owl:Thing"), a full IRI, a relative IRI, or an OBO ID
            (e.g., a string of the form "PO:0000003").
        """
        classIRI = self.expandIdentifier(class_id)

        # Get the class object.
        owlclass = self.df.getOWLClass(classIRI)

        declaxiom = self.df.getOWLDeclarationAxiom(owlclass)
        self.ontman.applyChange(AddAxiom(self.ontology, declaxiom))

        return _OntologyClass(classIRI, owlclass, self)
    
    def createNewDataProperty(self, prop_id):
        """
        Creates a new OWL data property, adds it to the ontology, and returns
        an associated _OntologyDataProperty object.

        prop_iri: The identifier for the new property.  Can be either an OWL
            API IRI object or a string containing: a prefix IRI (i.e., a curie,
            such as "owl:Thing"), a full IRI, or an OBO ID (e.g., a string of
            the form "PO:0000003").
        """
        propIRI = self.expandIdentifier(prop_id)

        owldprop = self.df.getOWLDataProperty(propIRI)

        declaxiom = self.df.getOWLDeclarationAxiom(owldprop)
        self.ontman.applyChange(AddAxiom(self.ontology, declaxiom))

        return _OntologyDataProperty(propIRI, owldprop, self)

    def createNewObjectProperty(self, prop_id):
        """
        Creates a new OWL object property, adds it to the ontology, and returns
        an associated _OntologyObjectProperty object.

        prop_iri: The identifier for the new property.  Can be either an OWL
            API IRI object or a string containing: a prefix IRI (i.e., a curie,
            such as "owl:Thing"), a full IRI, or an OBO ID (e.g., a string of
            the form "PO:0000003").
        """
        propIRI = self.expandIdentifier(prop_id)

        owloprop = self.df.getOWLObjectProperty(propIRI)

        declaxiom = self.df.getOWLDeclarationAxiom(owloprop)
        self.ontman.applyChange(AddAxiom(self.ontology, declaxiom))

        return _OntologyObjectProperty(propIRI, owloprop, self)

    def createNewAnnotationProperty(self, prop_id):
        """
        Creates a new OWL annotation property, adds it to the ontology, and
        returns an associated _OntologyAnnotationProperty object.

        prop_iri: The identifier for the new property.  Can be either an OWL
            API IRI object or a string containing: a prefix IRI (i.e., a curie,
            such as "owl:Thing"), a full IRI, or an OBO ID (e.g., a string of
            the form "PO:0000003").
        """
        propIRI = self.expandIdentifier(prop_id)

        owloprop = self.df.getOWLAnnotationProperty(propIRI)

        declaxiom = self.df.getOWLDeclarationAxiom(owloprop)
        self.ontman.applyChange(AddAxiom(self.ontology, declaxiom))

        return _OntologyAnnotationProperty(propIRI, owloprop, self)

    def addTermAxiom(self, owl_axiom):
        """
        Adds a new term axiom to this ontology.  In this context, "term axiom"
        means an axiom with an OWL class or property as its subject.  The
        argument "owl_axiom" should be an instance of an OWL API axiom object.
        """
        # If this is a label annotation, update the label lookup dictionary.
        if owl_axiom.isOfType(AxiomType.ANNOTATION_ASSERTION):
            if owl_axiom.getProperty().isLabel():
                labeltxt = owl_axiom.getValue().getLiteral()

                # If we are adding a label, we should be guaranteed that the
                # subject of the annotation is an IRI (i.e, not anonymous).
                subjIRI = owl_axiom.getSubject()
                if not(isinstance(subjIRI, IRI)):
                    raise RuntimeError('Attempted to add the label "'
                        + labeltxt + '" as an annotation of an anonymous class.')
                self.labelmap.add(labeltxt, subjIRI)

        self.ontman.applyChange(AddAxiom(self.ontology, owl_axiom))

    def removeEntity(self, entity, remove_annotations=True):
        """
        Removes an entity from the ontology (including its imports closure).
        Optionally, any annotations referencing the deleted entity can also be
        removed (this is the default behavior).

        entity: An OWL API entity object.
        remove_annotations: If True, annotations referencing the entity will
            also be removed.
        """
        ontset = self.ontology.getImportsClosure()
        for ont in ontset:
            # A set for gathering axioms to remove so that axioms can be
            # deleted after looping over an ontology's axioms rather than in
            # the loop, to avoid the risk of invalidating the iteration.
            del_axioms = HashSet()

            for axiom in ont.getAxioms():
                # See if this axiom is an annotation axiom.
                if axiom.getAxiomType() == AxiomType.ANNOTATION_ASSERTION:
                    if remove_annotations:
                        # Check if this annotation axiom refers to the target
                        # entity.
                        asubject = axiom.getSubject()
                        if isinstance(asubject, IRI):
                            if asubject.equals(entity.getIRI()):
                                del_axioms.add(axiom)
                # See if this axiom includes the target entity (e.g., a
                # declaration axiom for the target entity).
                elif axiom.getSignature().contains(entity):
                    del_axioms.add(axiom)

            self.ontman.removeAxioms(ont, del_axioms)

    def setOntologyID(self, ont_iri):
        """
        Sets the ID for the ontology (i.e., the value of the "rdf:about"
        attribute).
        
          ont_iri: The IRI (i.e., ID) of the ontology.  Can be either an IRI
                   object or a string.
        """
        ontIRI = self.expandIRI(ont_iri)

        newoid = OWLOntologyID(Optional.fromNullable(ontIRI), Optional.absent())
        self.ontman.applyChange(SetOntologyID(self.ontology, newoid))

    def addImport(self, source_iri, load_import=True):
        """
        Adds an OWL import statement to this ontology.

        source_iri: The IRI of the source ontology.  Can be either an IRI
            object or a string.
        load_import: If True, the new import will be automatically loaded and
            its terms labels will be added to the internal LabelMap.
        """
        sourceIRI = self.expandIRI(source_iri)
        owlont = self.getOWLOntology()
        
        # Check if the imported ontology is already included in an imports
        # declaration.  If so, there's nothing to do.
        if owlont.getDirectImportsDocuments().contains(sourceIRI):
            return

        importdec = self.df.getOWLImportsDeclaration(sourceIRI)
        self.ontman.applyChange(
            AddImport(owlont, importdec)
        )

        if load_import:
            # Manually load the newly added import.
            try:
                importont = self.ontman.loadOntology(sourceIRI)
            except (
                OWLOntologyFactoryNotFoundException,
                OWLOntologyCreationIOException
            ) as err:
                raise RuntimeError('The import module ontology at <{0}> could not be loaded.  Please make sure that the IRI is correct and that the import module ontology is accessible.'.format(source_iri))

            # Add the imported ontology's terms to the LabelMap.
            self.labelmap.addOntologyTerms(importont)

    def mergeOntology(self, source_iri):
        """
        Merges the axioms from an external ontology into this ontology.  Also
        manages collisions with import declarations, so that if the merged
        ontology is declared as an import in the target ontology (i.e., this
        ontology), the import declaration will be deleted.

        source_iri: The IRI of the source ontology.  Can be either an IRI
            object or a string.
        """
        sourceIRI = self.expandIRI(source_iri)
        owlont = self.getOWLOntology()

        try:
            importont = self.ontman.loadOntology(sourceIRI)
        except (
            OWLOntologyFactoryNotFoundException,
            OWLOntologyCreationIOException
        ) as err:
            raise RuntimeError('The import module ontology at <{0}> could not be loaded.  Please make sure that the IRI is correct and that the import module ontology is accessible.'.format(source_iri))

        # Add the axioms from the external ontology to this ontology.
        axiomset = importont.getAxioms(ImportsEnum.EXCLUDED)
        self.ontman.addAxioms(owlont, axiomset)

        # See if the merged ontology was already in the imports declarations
        # for the target ontology; if so, remove it.  Do this by gathering
        # invalidated imports declarations into a set so that they can be
        # deleted after looping over an ontology's imports declarations rather
        # than in the loop, to avoid the risk of invalidating the iteration.
        del_decs = HashSet()
        for importsdec in owlont.getImportsDeclarations():
            if importsdec.getIRI().equals(sourceIRI):
                del_decs.add(importsdec)

        for dec in del_decs:
            self.ontman.applyChange(RemoveImport(owlont, dec))

        if del_decs.isEmpty():
            # If the merged ontology was not already imported, add its terms to
            # the LabelMap.
            self.labelmap.addOntologyTerms(importont)

    def _getGeneratorsList(self, reasoner):
        """
        Returns a list of AxiomGenerators for a reasoner that match the
        capabilities of the reasoner.

        reasoner: A reasoner instance.
        """
        # By default, only use generators that are supported by the ELK
        # reasoner.  Assume that all reasoners have these capabilities.
        generators = [
            InferredSubClassAxiomGenerator(),
            InferredEquivalentClassAxiomGenerator(),
            InferredClassAssertionAxiomGenerator(),
            InferredDisjointClassesAxiomGenerator()
        ]
        
        # Check for data property hierarchy inferencing support.
        hasmethod = True
        try:
            testprop = self.df.getOWLDataProperty(IRI.create('test'))
            reasoner.getSuperDataProperties(testprop, True)
        except UnsupportedOperationException as err:
            hasmethod = False
        if hasmethod:
            generators.append(InferredSubDataPropertyAxiomGenerator())

        # Check for object property hierarchy inferencing support.
        hasmethod = True
        try:
            testprop = self.df.getOWLObjectProperty(IRI.create('test'))
            reasoner.getSuperObjectProperties(testprop, True)
        except UnsupportedOperationException as err:
            hasmethod = False
        if hasmethod:
            generators.append(InferredSubObjectPropertyAxiomGenerator())

        return generators

    def addInferredAxioms(self, reasoner, annotate=False):
        """
        Runs a reasoner on this ontology and adds the inferred axioms.  The
        reasoner instance should be obtained from one of the get*Reasoner()
        methods of this ontology.

        reasoner: A reasoner instance.
        annotate: If true, annotate inferred axioms to mark them as inferred.
        """
        # The general approach is to first get the set of all axioms in the
        # ontology prior to reasoning so that this set can be used for
        # de-duplication later.  Then, inferred axioms are added to a new
        # ontology.  This makes it easy to compare explicit and inferred
        # axioms and to annotate inferred axioms.  Trivial axioms are removed
        # from the inferred axiom set, and the inferred axioms are merged into
        # the main ontology.

        owlont = self.getOWLOntology()
        oldaxioms = owlont.getAxioms(ImportsEnum.INCLUDED)

        reasoner.precomputeInferences(InferenceType.CLASS_HIERARCHY)
        reasoner.precomputeInferences(InferenceType.CLASS_ASSERTIONS)

        generators = self._getGeneratorsList(reasoner)
        iog = InferredOntologyGenerator(reasoner, generators)

        inferredont = self.ontman.createOntology()
        iog.fillOntology(self.df, inferredont)

        # Delete axioms in the inferred set that are explicitly stated in the
        # source ontology (or its imports closure).
        delaxioms = HashSet()
        for axiom in inferredont.getAxioms():
            if oldaxioms.contains(axiom):
                delaxioms.add(axiom)
        self.ontman.removeAxioms(inferredont, delaxioms)

        # Delete trivial axioms (e.g., subclass of owl:Thing, etc.).
        trivial_entities = [
            self.df.getOWLThing(), self.df.getOWLTopDataProperty(),
            self.df.getOWLTopObjectProperty()
        ]
        delaxioms.clear()
        for axiom in inferredont.getAxioms():
            for trivial_entity in trivial_entities:
                if axiom.containsEntityInSignature(trivial_entity):
                    delaxioms.add(axiom)
                    break
        self.ontman.removeAxioms(inferredont, delaxioms)

        if annotate:
            # Annotate all of the inferred axioms.
            annotprop = self.df.getOWLAnnotationProperty(self.INFERRED_ANNOT_IRI)
            annotval = self.df.getOWLLiteral('true')
            for axiom in inferredont.getAxioms():
                annot = self.df.getOWLAnnotation(annotprop, annotval)
                newaxiom = axiom.getAnnotatedAxiom(HashSet([annot]))
                self.ontman.removeAxiom(inferredont, axiom)
                self.ontman.addAxiom(inferredont, newaxiom)

        # Merge the inferred axioms into the main ontology.
        self.ontman.addAxioms(owlont, inferredont.getAxioms())

    def setOntologySource(self, source_iri):
        """
        Sets the value of the "dc:source" annotation property for this ontology.

          source_iri: The IRI of the source ontology.  Can be either an IRI
                      object or a string.
        """
        sourceIRI = self.expandIRI(source_iri)

        sourceprop = self.df.getOWLAnnotationProperty(self.SOURCE_PROP_IRI)
        s_annot = self.df.getOWLAnnotation(sourceprop, sourceIRI)
        self.ontman.applyChange(
            AddOntologyAnnotation(self.getOWLOntology(), s_annot)
        )

    def saveOntology(self, filepath):
        """
        Saves the ontology to a file.
        """
        oformat = RDFXMLDocumentFormat()
        foutputstream = FileOutputStream(File(filepath))
        self.ontman.saveOntology(self.ontology, oformat, foutputstream)
        foutputstream.close()

    def getELKReasoner(self):
        """
        Returns an instance of an ELK reasoner for this ontology.
        """
        rfact = ElkReasonerFactory()

        return rfact.createReasoner(self.getOWLOntology())

    def getHermitReasoner(self):
        """
        Returns an instance of a HermiT reasoner for this ontology.
        """
        rfact = HermiT.ReasonerFactory()

        return rfact.createReasoner(self.getOWLOntology())
    
    def extractModule(self, signature, mod_iri):
        """
        Extracts a module that is a subset of the entities in this ontology.
        The result is returned as an Ontology object.

        signature: A Java Set of all entities to include in the module.
        mod_iri: The IRI for the extracted ontology module.  Can be either an
            IRI object or a string.
        """
        modIRI = self.expandIRI(mod_iri)

        slme = SyntacticLocalityModuleExtractor(
            self.ontman, self.getOWLOntology(), ModuleType.STAR
        )
        modont = Ontology(slme.extractAsOntology(signature, modIRI))

        # Add an annotation for the source of the module.
        sourceIRI = None
        ontid = self.getOWLOntology().getOntologyID()
        if ontid.getVersionIRI().isPresent():
            sourceIRI = ontid.getVersionIRI().get()
        elif ontid.getOntologyIRI().isPresent():
            sourceIRI = ontid.getOntologyIRI().get()

        if sourceIRI != None:
            modont.setOntologySource(sourceIRI)

        return modont

