# Copyright (C) 2017 Brian J. Stucky
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


# Python imports.
from idresolver import IDResolver
from ontology import Ontology
from ontology_entities import (
    CLASS_ENTITY, DATAPROPERTY_ENTITY, OBJECTPROPERTY_ENTITY,
    ANNOTATIONPROPERTY_ENTITY, INDIVIDUAL_ENTITY
)
from ontology_entities import _OntologyClass, _OntologyDataProperty
from ontology_entities import _OntologyObjectProperty, _OntologyAnnotationProperty
from ontology_entities import _OntologyIndividual, _OntologyEntity
from reasoner_manager import ReasonerManager
from observable import Observable

# Java imports.
from java.io import File, FileOutputStream
from java.util import HashSet
from org.semanticweb.owlapi.apibinding import OWLManager
from org.semanticweb.owlapi.model import IRI, OWLOntologyID
from org.semanticweb.owlapi.model import AddAxiom, AddImport, RemoveImport
from org.semanticweb.owlapi.model import SetOntologyID, AxiomType, OWLOntology
from org.semanticweb.owlapi.model import AddOntologyAnnotation
from org.semanticweb.owlapi.formats import RDFXMLDocumentFormat
from uk.ac.manchester.cs.owlapi.modularity import SyntacticLocalityModuleExtractor
from uk.ac.manchester.cs.owlapi.modularity import ModuleType
from com.google.common.base import Optional
from org.semanticweb.owlapi.io import OWLOntologyCreationIOException
from org.semanticweb.owlapi.model import OWLOntologyFactoryNotFoundException
from org.semanticweb.owlapi.model.parameters import Imports as ImportsEnum
from org.semanticweb.owlapi.model import EntityType


# Define constants for the supported extraction methods.
class _ExtractMethodsStruct:
    # The STAR syntactic locality extraction method.
    LOCALITY = 0
    # Extract single entities without any other axioms (except annotations).
    SINGLE = 1
    # Extract entities and their superclass/superproperty hierarchies without
    # any other axioms (except annotations).
    HIERARCHY = 2

    # Combine all supported methods in a single tuple.
    all_methods = (LOCALITY, SINGLE, HIERARCHY)

    # Define string values that map to the extraction methods.
    strings = {
        'locality': LOCALITY,
        'single': SINGLE,
        'hierarchy': HIERARCHY
    }
methods = _ExtractMethodsStruct()


class ModuleExtractor:
    """
    Extracts import "modules" from existing OWL ontologies.
    """
    def __init__(self, ontology_source):
        """
        Initialize this ModuleExtractor instance.  The argument
        "ontology_source" should be an instance of ontopilot.Ontology.
        """
        self.ontology = ontology_source
        self.owlont = self.ontology.getOWLOntology()

        # Initialize data structures for holding the extraction signatures.
        self.signatures = {}
        self.clearSignatures()

    def clearSignatures(self):
        """
        Resets all signature sets to empty.
        """
        for method in methods.all_methods:
            self.signatures[method] = set()

    def addEntity(self, entity_id, method, include_branch=False):
        """
        Adds an entity to the module signature.  If include_branch is True, all
        descendants of the entity will be retrieved and added to the signature.
        The final module will ensure that all parent/child relationships in the
        retrieved branch are preserved.

        entity_id: The identifier of the entity.  Can be either an OWL API IRI
            object or a string containing: a label (with or without a prefix),
            a prefix IRI (i.e., a curie, such as "owl:Thing"), a relative IRI,
            a full IRI, or an OBO ID (e.g., a string of the form "PO:0000003").
            Labels should be enclosed in single quotes (e.g., 'label text' or
            prefix:'label txt').
        method: The extraction method to use for this entity.
        include_branch: If True, all descendants of the entity will also be
            added to the signature.
        """
        entity = self.ontology.getExistingEntity(entity_id)
        if entity == None:
            raise RuntimeError(
                'The entity {0} could not be found in the source '
                'ontology.'.format(entity_id)
            )

        self.signatures[method].add(entity.getOWLAPIObj())

    def extractModule(self, mod_iri):
        """
        Extracts a module that is a subset of the entities in the source
        ontology.  The result is returned as an Ontology object.

        mod_iri: The IRI for the extracted ontology module.  Can be either an
            IRI object or a string containing a relative IRI, prefix IRI, or
            full IRI.
        """
        modont = Ontology(self.ontology.ontman.createOntology())
        modont.setOntologyID(mod_iri)

        # Do the syntactic locality extraction.  Only do the extraction if the
        # signature set is non-empty.  The OWL API module extractor will
        # produce a non-empty module even for an empty signature set.
        if len(self.signatures[methods.LOCALITY]) > 0:
            slme = SyntacticLocalityModuleExtractor(
                self.ontology.ontman, self.owlont, ModuleType.STAR
            )
            mod_axioms = slme.extract(self.signatures[methods.LOCALITY])
            for axiom in mod_axioms:
                modont.addEntityAxiom(axiom)

        # Process the hierarchy extractions.
        hierset, axiomset = self._getEntitiesInHierarchies(
            self.signatures[methods.HIERARCHY]
        )

        # Add the entities from the entity hierarchies to the set of entities
        # to extract individually.
        self.signatures[methods.SINGLE].update(hierset)

        # Do all single-entity extractions.
        self._extractSingleEntities(self.signatures[methods.SINGLE], modont)

        # Add any subclass/subproperty axioms.
        for axiom in axiomset:
            modont.addEntityAxiom(axiom)

        # Add an annotation for the source of the module.
        sourceIRI = None
        ontid = self.owlont.getOntologyID()
        if ontid.getVersionIRI().isPresent():
            sourceIRI = ontid.getVersionIRI().get()
        elif ontid.getOntologyIRI().isPresent():
            sourceIRI = ontid.getOntologyIRI().get()

        if sourceIRI != None:
            modont.setOntologySource(sourceIRI)

        return modont

    def _getBranch(self, root_entity):
        """
        Retrieves all entities that are descendants of the root entity.
        Returns two sets: 1) a set of all entities in the branch; and 2) a set
        of all subclass/subproperty axioms relating the entities in the branch.

        root_entity: An ontopilot.OntologyEntity object.
        """
        # Initialize the results sets.
        br_entset = set()
        br_axiomset = set()

        # Initialize a list to serve as a stack for tracking the "recursion"
        # through the branch.
        stack = [root_entity]

        while len(traverse) > 0:
            entity = stack.pop()

            br_entset.add(entity)

            if entity.getTypeConst() == CLASS_ENTITY:
                axioms = self.owlont.getSubClassAxiomsForSuperClass(
                    entity.getOWLAPIObj()
                )
                for axiom in axioms:
                    sub_ce = axiom.getSubClass()
                    if not(sub_ce.isAnonymous()):
                        subclass = self.ontology.getExistingClass(
                            sub_ce.asOWLClass().getIRI()
                        )
                        if (subclass != None):
                            axiomset.add(axiom)

                            # Check whether the child class has already been
                            # processed so we don't get stuck in cyclic
                            # relationship graphs.
                            if not(superclass in hierset):
                                signature.add(superclass)


    def _getEntitiesInHierarchies(self, signature):
        """
        Returns two sets: 1) a set of OntologyEntity objects that includes the
        entities in the signature set and all entities in the ancestor
        hierarchies of the entities in the signature set; and 2) a set of all
        subclass/subproperty axioms needed to create the desired entity
        hierarchies.

        signature: A set of OWL API OWLEntity objects.
        """
        hierset = set()
        axiomset = set()

        while len(signature) > 0:
            entity = signature.pop()

            hierset.add(entity)

            if entity.getEntityType() == EntityType.CLASS:
                axioms = self.owlont.getSubClassAxiomsForSubClass(entity)
                for axiom in axioms:
                    super_ce = axiom.getSuperClass()
                    if not(super_ce.isAnonymous()):
                        superclass = super_ce.asOWLClass()
                        axiomset.add(axiom)

                        # Check whether the parent class has already been
                        # processed so we don't get stuck in cyclic
                        # relationship graphs.
                        if not(superclass in hierset):
                            signature.add(superclass)

            elif entity.getEntityType() == EntityType.OBJECT_PROPERTY:
                axioms = self.owlont.getObjectSubPropertyAxiomsForSubProperty(
                    entity
                )
                for axiom in axioms:
                    super_pe = axiom.getSuperProperty()
                    if not(super_pe.isAnonymous()):
                        superprop = super_pe.asOWLObjectProperty()
                        axiomset.add(axiom)

                        # Check whether the parent property has already been
                        # processed so we don't get stuck in cyclic
                        # relationship graphs.
                        if not(superprop in hierset):
                            signature.add(superprop)

            elif entity.getEntityType() == EntityType.DATA_PROPERTY:
                axioms = self.owlont.getDataSubPropertyAxiomsForSubProperty(
                    entity
                )
                for axiom in axioms:
                    super_pe = axiom.getSuperProperty()
                    if not(super_pe.isAnonymous()):
                        superprop = super_pe.asOWLDataProperty()
                        axiomset.add(axiom)

                        # Check whether the parent property has already been
                        # processed so we don't get stuck in cyclic
                        # relationship graphs.
                        if not(superprop in hierset):
                            signature.add(superprop)

            elif entity.getEntityType() == EntityType.ANNOTATION_PROPERTY:
                axioms = self.owlont.getSubAnnotationPropertyOfAxioms(entity)
                for axiom in axioms:
                    superprop = axiom.getSuperProperty()
                    axiomset.add(axiom)

                    # Check whether the parent property has already been
                    # processed so we don't get stuck in cyclic relationship
                    # graphs.
                    if not(superprop in hierset):
                        signature.add(superprop)

        return (hierset, axiomset)

    def _extractSingleEntities(self, signature, target):
        """
        Extracts entities from the source ontology using the single-entity
        extraction method, which pulls individual entities without any
        associated axioms (except for annotations).  Annotation properties that
        are used to annotate entities in the signature will also be extracted
        from the source ontology.

        signature: A set of OWL API OWLEntity objects.
        target: The target module ontopilot.Ontology object.
        """
        owltarget = target.getOWLOntology()

        rdfslabel = self.ontology.df.getRDFSLabel()

        while len(signature) > 0:
            owlent = signature.pop()

            # Get the declaration axiom for this entity and add it to the
            # target ontology.
            ontset = self.owlont.getImportsClosure()
            for ont in ontset:
                dec_axioms = ont.getDeclarationAxioms(owlent)
                for axiom in dec_axioms:
                    target.addEntityAxiom(axiom)

            # Get all annotation axioms for this entity and add them to the
            # target ontology.
            for ont in ontset:
                annot_axioms = ont.getAnnotationAssertionAxioms(owlent.getIRI())

                for annot_axiom in annot_axioms:
                    target.addEntityAxiom(annot_axiom)

                    # Check if the relevant annotation property is already
                    # included in the target ontology.  If not, add it to the
                    # set of terms to extract.

                    # Ignore rdfs:label since it is always included.
                    if annot_axiom.getProperty().equals(rdfslabel):
                        continue

                    prop_iri = annot_axiom.getProperty().getIRI()

                    if target.getExistingAnnotationProperty(prop_iri) == None:
                        annot_ent = self.ontology.getExistingAnnotationProperty(prop_iri)
                        # Built-in annotation properties, such as rdfs:label,
                        # will not "exist" because they have no declaration
                        # axioms, so we need to check for this.
                        if annot_ent != None:
                            signature.add(annot_ent.getOWLAPIObj())
