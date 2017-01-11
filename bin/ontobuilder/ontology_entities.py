#
# Provides convenience classes that "wrap" OWL API classes and properties and
# implements a higher-level interface for interacting with OWL ontologies.
# None of these classes should be instantiated directly; rather, instances
# should be obtained from the public methods of the ontology.Ontology class.
#

# Python imports.
from obohelper import oboIDToIRI
from mshelper import ManchesterSyntaxParserHelper

# Java imports.
from org.semanticweb.owlapi.manchestersyntax.renderer import ParserException


# Constants for defining the types of supported ontology entity objects.
CLASS_ENTITY = 0
DATAPROPERTY_ENTITY = 1
OBJECTPROPERTY_ENTITY = 2
ANNOTATIONPROPERTY_ENTITY = 3


class _OntologyClass:
    """
    Provides a high-level interface to the OWL API's ontology object system
    for OWL classes.  Conceptually, instances of this class represent a single
    OWL class in an OWL ontology.  This class should not be instantiated
    directly; instead, instances should be obtained through Ontology's public
    interface.
    """
    # The IRI for the property for definition annotations.
    DEFINITION_IRI = oboIDToIRI('IAO:0000115')

    def __init__(self, classIRI, classobj, ontology):
        """
        Initializes this _OntologyClass.

          class_iri: The IRI object of the class.
          classobj: The OWL API class object of the class.
          ontology: The ontology to which this class belongs.
        """
        self.ontology = ontology
        self.df = ontology.df
        self.classIRI = classIRI
        self.classobj = classobj

    def getTypeConst(self):
        return CLASS_ENTITY
        
    def addDefinition(self, deftxt):
        """
        Adds a definition annotation to this class (i.e., adds an annotation
        for "definition", IAO:0000115).
        """
        deftxt = deftxt.strip()

        defannot = self.df.getOWLAnnotation(
            self.df.getOWLAnnotationProperty(self.DEFINITION_IRI),
            self.df.getOWLLiteral(deftxt)
        )
        annotaxiom = self.df.getOWLAnnotationAssertionAxiom(self.classIRI, defannot)

        self.ontology.addTermAxiom(annotaxiom)

    def addLabel(self, labeltxt):
        """
        Adds an rdfs:label for this class.
        """
        labeltxt = labeltxt.strip()

        labelannot = self.df.getOWLAnnotation(
            self.df.getRDFSLabel(), self.df.getOWLLiteral(labeltxt, 'en')
        )
        annotaxiom = self.df.getOWLAnnotationAssertionAxiom(self.classIRI, labelannot)

        self.ontology.addTermAxiom(annotaxiom)

    def addComment(self, commenttxt):
        """
        Adds an rdfs:comment for this class.
        """
        commenttxt = commenttxt.strip()

        commentannot = self.df.getOWLAnnotation(
            self.df.getRDFSComment(), self.df.getOWLLiteral(commenttxt, 'en')
        )
        annotaxiom = self.df.getOWLAnnotationAssertionAxiom(self.classIRI, commentannot)

        self.ontology.addTermAxiom(annotaxiom)

    def addSuperclass(self, parent_id):
        """
        Adds a parent class for this class.

        parent_id: The identifier of the parent class.   Can be either an OWL
            API IRI object or a string containing: a prefix IRI (i.e., a curie,
            such as "owl:Thing"), a full IRI, or an OBO ID (e.g., a string of
            the form "PO:0000003").
        """
        parentIRI = self.ontology.expandIdentifier(parent_id)

        # Get the OWLClass object of the parent class, making sure that it is
        # actually defined.
        parentclass = self.ontology.getExistingClass(parentIRI)
        if parentclass == None:
            raise RuntimeError('The designated superclass, ' + str(parent_id)
                    + ', could not be found in the source ontology.')
        
        # Add the subclass axiom to the ontology.
        newaxiom = self.df.getOWLSubClassOfAxiom(self.classobj, parentclass)
        self.ontology.addTermAxiom(newaxiom)

    def _getClassExpressions(self, manchester_exps):
        """
        Given a string containing one or more class expressions in Manchester
        Syntax, returns a list containing corresponding OWL API class
        expression objects.

        manchester_exps: A string containing MS "description" productions.
        """
        try:
            #self.ontology.mparser = ManchesterSyntaxTool(self.ontology.ontology)
            #cexp = self.ontology.mparser.parseManchesterExpression(formaldef)
            parser = ManchesterSyntaxParserHelper(self.ontology)
            cexps = parser.parseClassExpressions(manchester_exps);
        except ParserException as err:
            print err
            raise RuntimeError('Error parsing "' + err.getCurrentToken()
                    + '" at line ' + str(err.getLineNumber()) + ', column '
                    + str(err.getColumnNumber())
                    + ' of the class expression (Manchester Syntax expected).')

        return cexps

    def addSubclassOf(self, manchester_exps):
        """
        Adds one or more class expressions as "subclass of" axioms.  The class
        expressions should be written in Manchester Syntax (MS), and if there
        is more than one class expression, the expressions should be separated
        by blank lines containing a semicolon.

        manchester_exps: A string containing MS "description" productions.
        """
        if manchester_exps != '':
            cexps = self._getClassExpressions(manchester_exps)

            for cexp in cexps:
                eaxiom = self.df.getOWLSubClassOfAxiom(self.classobj, cexp)
                self.ontology.addTermAxiom(eaxiom)

    def addEquivalentTo(self, manchester_exps):
        """
        Adds one or more class expressions as equivalency axioms.  The class
        expressions should be written in Manchester Syntax (MS), and if there
        is more than one class expression, the expressions should be separated
        by blank lines containing a semicolon.

        manchester_exps: A string containing MS "description" productions.
        """
        if manchester_exps != '':
            cexps = self._getClassExpressions(manchester_exps)

            for cexp in cexps:
                eaxiom = self.df.getOWLEquivalentClassesAxiom(self.classobj, cexp)
                self.ontology.addTermAxiom(eaxiom)

    def addDisjointWith(self, manchester_exps):
        """
        Adds one or more class expressions as "disjoint with" axioms.  The
        class expressions should be written in Manchester Syntax (MS), and if
        there is more than one class expression, the expressions should be
        separated by blank lines containing a semicolon.

        manchester_exps: A string containing MS "description" productions.
        """
        if manchester_exps != '':
            cexps = self._getClassExpressions(manchester_exps)

            for cexp in cexps:
                axiom = self.df.getOWLDisjointClassesAxiom(self.classobj, cexp)
                self.ontology.addTermAxiom(axiom)


class _OntologyDataProperty:
    """
    Provides a high-level interface to the OWL API's ontology object system
    for OWL data properties.  Conceptually, instances of this class represent a
    single OWL data property in an OWL ontology.  This class should not be
    instantiated directly; instead, instances should be obtained through
    Ontology's public interface.
    """
    # The IRI for the property for definition annotations.
    DEFINITION_IRI = oboIDToIRI('IAO:0000115')

    def __init__(self, propIRI, propobj, ontology):
        """
        Initializes this _OntologyDataProperty.

          class_iri: The IRI object of the property.
          propobj: The OWL API property object of the property.
          ontology: The ontology to which this property belongs.
        """
        self.ontology = ontology
        self.df = ontology.df
        self.propIRI = propIRI
        self.propobj = propobj
        
    def getTypeConst(self):
        return DATAPROPERTY_ENTITY
        
    def addDefinition(self, deftxt):
        """
        Adds a definition annotation to this property (i.e., adds an annotation
        for "definition", IAO:0000115).
        """
        deftxt = deftxt.strip()

        defannot = self.df.getOWLAnnotation(
            self.df.getOWLAnnotationProperty(self.DEFINITION_IRI),
            self.df.getOWLLiteral(deftxt)
        )
        annotaxiom = self.df.getOWLAnnotationAssertionAxiom(self.propIRI, defannot)

        self.ontology.addTermAxiom(annotaxiom)

    def addLabel(self, labeltxt):
        """
        Adds an rdfs:label for this property.
        """
        labeltxt = labeltxt.strip()

        labelannot = self.df.getOWLAnnotation(
            self.df.getRDFSLabel(), self.df.getOWLLiteral(labeltxt, 'en')
        )
        annotaxiom = self.df.getOWLAnnotationAssertionAxiom(self.propIRI, labelannot)

        self.ontology.addTermAxiom(annotaxiom)

    def addComment(self, commenttxt):
        """
        Adds an rdfs:comment for this property.
        """
        commenttxt = commenttxt.strip()

        commentannot = self.df.getOWLAnnotation(
            self.df.getRDFSComment(), self.df.getOWLLiteral(commenttxt, 'en')
        )
        annotaxiom = self.df.getOWLAnnotationAssertionAxiom(self.propIRI, commentannot)

        self.ontology.addTermAxiom(annotaxiom)

    def addSuperproperty(self, parent_id):
        """
        Adds a parent property for this property.

        parent_id: The identifier of the parent property.  Can be either an OWL
            API IRI object or a string containing: a prefix IRI (i.e., a curie,
            such as "owl:Thing"), a full IRI, or an OBO ID (e.g., a string of
            the form "PO:0000003").
        """
        parentIRI = self.ontology.expandIdentifier(parent_id)

        # Get the OWL property object of the parent, making sure that it is
        # actually defined.
        parentprop = self.ontology.getExistingDataProperty(parentIRI)
        if parentprop == None:
            raise RuntimeError('The designated superproperty, ' + str(parent_id)
                    + ', could not be found in the source ontology.')

        # Add the subproperty axiom to the ontology.
        newaxiom = self.df.getOWLSubDataPropertyOfAxiom(self.propobj, parentprop)
        self.ontology.addTermAxiom(newaxiom)

    def addDomain(self, domain_id):
        """
        Creates a domain axiom for this data property.

        domain_id: The identifier of a class.  Can be either an OWL API IRI
            object or a string containing: a prefix IRI (i.e., a curie, such as
            "owl:Thing"), a full IRI, or an OBO ID (e.g., a string of the form
            "PO:0000003").
        """
        domainIRI = self.ontology.expandIdentifier(domain_id)

        # Get the class object for the domain.  We do not require that the
        # class is already declared, because properties might have to be
        # declared before the classes to which they apply.
        classobj = self.df.getOWLClass(domainIRI)

        # Add the declaration axiom.
        daxiom = self.df.getOWLDataPropertyDomainAxiom(self.propobj, classobj)
        self.ontology.addTermAxiom(daxiom)

    def addRange(self, datarange_exp):
        """
        Creates a range axiom for this data property.

        datarange_exp: A text string containing a valid Manchester Syntax
            "dataRange" production.
        """
        if datarange_exp != '':
            try:
                parser = ManchesterSyntaxParserHelper(self.ontology)

                # Parse the expression to get an OWLDataRange object.
                datarange = parser.parseDataRange(datarange_exp);
            except ParserException as err:
                print err
                raise RuntimeError('Error parsing "' + err.getCurrentToken()
                        + '" at line ' + str(err.getLineNumber()) + ', column '
                        + str(err.getColumnNumber())
                        + ' of the data property range (Manchester Syntax expected).')

            # Add the range declaration axiom.
            raxiom = self.df.getOWLDataPropertyRangeAxiom(self.propobj, datarange)
            self.ontology.addTermAxiom(raxiom)

    def addDisjointWith(self, prop_id):
        """
        Sets this property as disjoint with another property.

        prop_id: The identifier of a data property.  Can be either an OWL API
            IRI object or a string containing: a prefix IRI (i.e., a curie,
            such as "owl:Thing"), a full IRI, or an OBO ID (e.g., a string of
            the form "PO:0000003").
        """
        propIRI = self.ontology.expandIdentifier(prop_id)

        # Get the property object.  We do not require that the property is
        # already declared, because a "disjoint with" axiom might have to be
        # defined before both properties in the axiom have been defined.
        dpropobj = self.df.getOWLDataProperty(propIRI)

        # Add the "disjoint with" axiom.
        daxiom = self.df.getOWLDisjointDataPropertiesAxiom(self.propobj, dpropobj)
        self.ontology.addTermAxiom(daxiom)

    def makeFunctional(self):
        """
        Makes this data property a functional property.
        """
        faxiom = self.df.getOWLFunctionalDataPropertyAxiom(self.propobj)
        self.ontology.addTermAxiom(faxiom)


class _OntologyObjectProperty:
    """
    Provides a high-level interface to the OWL API's ontology object system for
    OWL object properties.  Conceptually, instances of this class represent a
    single OWL object property in an OWL ontology.  This class should not be
    instantiated directly; instead, instances should be obtained through
    Ontology's public interface.
    """
    # The IRI for the property for definition annotations.
    DEFINITION_IRI = oboIDToIRI('IAO:0000115')

    def __init__(self, propIRI, propobj, ontology):
        """
        Initializes this _OntologyObjectProperty.

          class_iri: The IRI object of the property.
          classobj: The OWL API class object of the property.
          ontology: The ontology to which this property belongs.
        """
        self.ontology = ontology
        self.df = ontology.df
        self.propIRI = propIRI
        self.propobj = propobj
        
    def getTypeConst(self):
        return OBJECTPROPERTY_ENTITY
        
    def addDefinition(self, deftxt):
        """
        Adds a definition annotation to this property (i.e., adds an annotation
        for "definition", IAO:0000115).
        """
        deftxt = deftxt.strip()

        defannot = self.df.getOWLAnnotation(
            self.df.getOWLAnnotationProperty(self.DEFINITION_IRI),
            self.df.getOWLLiteral(deftxt)
        )
        annotaxiom = self.df.getOWLAnnotationAssertionAxiom(self.propIRI, defannot)

        self.ontology.addTermAxiom(annotaxiom)

    def addLabel(self, labeltxt):
        """
        Adds an rdfs:label for this property.
        """
        labeltxt = labeltxt.strip()

        labelannot = self.df.getOWLAnnotation(
            self.df.getRDFSLabel(), self.df.getOWLLiteral(labeltxt, 'en')
        )
        annotaxiom = self.df.getOWLAnnotationAssertionAxiom(self.propIRI, labelannot)

        self.ontology.addTermAxiom(annotaxiom)

    def addComment(self, commenttxt):
        """
        Adds an rdfs:comment for this property.
        """
        commenttxt = commenttxt.strip()

        commentannot = self.df.getOWLAnnotation(
            self.df.getRDFSComment(), self.df.getOWLLiteral(commenttxt, 'en')
        )
        annotaxiom = self.df.getOWLAnnotationAssertionAxiom(self.propIRI, commentannot)

        self.ontology.addTermAxiom(annotaxiom)

    def addSuperproperty(self, parent_id):
        """
        Adds a parent property for this property.

        parent_id: The identifier of the parent property.  Can be either an OWL
            API IRI object or a string containing: a prefix IRI (i.e., a curie,
            such as "owl:Thing"), a full IRI, or an OBO ID (e.g., a string of
            the form "PO:0000003").
        """
        parentIRI = self.ontology.expandIdentifier(parent_id)

        # Get the OWL property object of the parent, making sure that it is
        # actually defined.
        parentprop = self.ontology.getExistingObjectProperty(parentIRI)
        if parentprop == None:
            raise RuntimeError('The designated superproperty, ' + str(parent_id)
                    + ', could not be found in the source ontology.')

        # Add the subproperty axiom to the ontology.
        newaxiom = self.df.getOWLSubObjectPropertyOfAxiom(self.propobj, parentprop)
        self.ontology.addTermAxiom(newaxiom)

    def setDomain(self, domain_id):
        """
        Sets the domain of this property.

        domain_id: The identifier of a class.  Can be either an OWL API IRI
            object or a string containing: a prefix IRI (i.e., a curie, such as
            "owl:Thing"), a full IRI, or an OBO ID (e.g., a string of the form
            "PO:0000003").
        """
        domainIRI = self.ontology.expandIdentifier(domain_id)

        # Get the class object for the domain.  We do not require that the
        # class is already declared, because properties might have to be
        # declared before the classes to which they apply.
        classobj = self.df.getOWLClass(domainIRI)

        # Add the declaration axiom.
        daxiom = self.df.getOWLObjectPropertyDomainAxiom(self.propobj, classobj)
        self.ontology.addTermAxiom(daxiom)

    def setRange(self, range_id):
        """
        Sets the range for this property.

        range_id: The identifier of a class.  Can be either an OWL API IRI
            object or a string containing: a prefix IRI (i.e., a curie, such as
            "owl:Thing"), a full IRI, or an OBO ID (e.g., a string of the form
            "PO:0000003").
        """
        rangeIRI = self.ontology.expandIdentifier(range_id)

        # Get the class object for the range.  We do not require that the
        # class is already declared, because properties might have to be
        # declared before the classes to which they apply.
        classobj = self.df.getOWLClass(rangeIRI)

        # Add the range declaration axiom.
        raxiom = self.df.getOWLObjectPropertyRangeAxiom(self.propobj, classobj)
        self.ontology.addTermAxiom(raxiom)

    def setInverse(self, inverse_id):
        """
        Sets the inverse of this property.

        inverse_id: The identifier of an object property.  Can be either an OWL
            API IRI object or a string containing: a prefix IRI (i.e., a curie,
            such as "owl:Thing"), a full IRI, or an OBO ID (e.g., a string of
            the form "PO:0000003").
        """
        inverseIRI = self.ontology.expandIdentifier(inverse_id)

        # Get the inverse property object.  We do not require that the property
        # is already declared, because an inverse axiom might have to be
        # defined before both properties in the axiom have been defined.
        inv_propobj = self.df.getOWLObjectProperty(inverseIRI)

        # Add the "inverse of" axiom.
        iaxiom = self.df.getOWLInverseObjectPropertiesAxiom(self.propobj, inv_propobj)
        self.ontology.addTermAxiom(iaxiom)

    def setDisjointWith(self, prop_id):
        """
        Sets this property as disjoint with another property.

        prop_id: The identifier of an object property.  Can be either an OWL
            API IRI object or a string containing: a prefix IRI (i.e., a curie,
            such as "owl:Thing"), a full IRI, or an OBO ID (e.g., a string of
            the form "PO:0000003").
        """
        propIRI = self.ontology.expandIdentifier(prop_id)

        # Get the property object.  We do not require that the property is
        # already declared, because a "disjoint with" axiom might have to be
        # defined before both properties in the axiom have been defined.
        dpropobj = self.df.getOWLObjectProperty(propIRI)

        # Add the "disjoint with" axiom.
        daxiom = self.df.getOWLDisjointObjectPropertiesAxiom(self.propobj, dpropobj)
        self.ontology.addTermAxiom(daxiom)

    def makeFunctional(self):
        """
        Makes this property a functional property.
        """
        paxiom = self.df.getOWLFunctionalObjectPropertyAxiom(self.propobj)
        self.ontology.addTermAxiom(paxiom)

    def makeInverseFunctional(self):
        """
        Makes this property an inverse functional property.
        """
        paxiom = self.df.getOWLInverseFunctionalObjectPropertyAxiom(self.propobj)
        self.ontology.addTermAxiom(paxiom)

    def makeReflexive(self):
        """
        Makes this property a reflexive property.
        """
        paxiom = self.df.getOWLReflexiveObjectPropertyAxiom(self.propobj)
        self.ontology.addTermAxiom(paxiom)

    def makeIrreflexive(self):
        """
        Makes this property an irreflexive property.
        """
        paxiom = self.df.getOWLIrreflexiveObjectPropertyAxiom(self.propobj)
        self.ontology.addTermAxiom(paxiom)

    def makeSymmetric(self):
        """
        Makes this property a symmetric property.
        """
        paxiom = self.df.getOWLSymmetricObjectPropertyAxiom(self.propobj)
        self.ontology.addTermAxiom(paxiom)

    def makeAsymmetric(self):
        """
        Makes this property an asymmetric property.
        """
        paxiom = self.df.getOWLAsymmetricObjectPropertyAxiom(self.propobj)
        self.ontology.addTermAxiom(paxiom)

    def makeTransitive(self):
        """
        Makes this property a transitive property.
        """
        paxiom = self.df.getOWLTransitiveObjectPropertyAxiom(self.propobj)
        self.ontology.addTermAxiom(paxiom)


class _OntologyAnnotationProperty:
    """
    Provides a high-level interface to the OWL API's ontology object system for
    OWL annotation properties.  Conceptually, instances of this class represent
    a single OWL annotation property in an OWL ontology.  This class should not
    be instantiated directly; instead, instances should be obtained through
    Ontology's public interface.
    """
    # The IRI for the property for definition annotations.
    DEFINITION_IRI = oboIDToIRI('IAO:0000115')

    def __init__(self, propIRI, propobj, ontology):
        """
        Initializes this _OntologyAnnotationProperty.

          class_iri: The IRI object of the property.
          propobj: The OWL API property object of the property.
          ontology: The ontology to which this property belongs.
        """
        self.ontology = ontology
        self.df = ontology.df
        self.propIRI = propIRI
        self.propobj = propobj
        
    def getTypeConst(self):
        return ANNOTATIONPROPERTY_ENTITY
        
    def addDefinition(self, deftxt):
        """
        Adds a definition annotation to this property (i.e., adds an annotation
        for "definition", IAO:0000115).
        """
        deftxt = deftxt.strip()

        defannot = self.df.getOWLAnnotation(
            self.df.getOWLAnnotationProperty(self.DEFINITION_IRI),
            self.df.getOWLLiteral(deftxt)
        )
        annotaxiom = self.df.getOWLAnnotationAssertionAxiom(self.propIRI, defannot)

        self.ontology.addTermAxiom(annotaxiom)

    def addLabel(self, labeltxt):
        """
        Adds an rdfs:label for this property.
        """
        labeltxt = labeltxt.strip()

        labelannot = self.df.getOWLAnnotation(
            self.df.getRDFSLabel(), self.df.getOWLLiteral(labeltxt, 'en')
        )
        annotaxiom = self.df.getOWLAnnotationAssertionAxiom(self.propIRI, labelannot)

        self.ontology.addTermAxiom(annotaxiom)

    def addComment(self, commenttxt):
        """
        Adds an rdfs:comment for this property.
        """
        commenttxt = commenttxt.strip()

        commentannot = self.df.getOWLAnnotation(
            self.df.getRDFSComment(), self.df.getOWLLiteral(commenttxt, 'en')
        )
        annotaxiom = self.df.getOWLAnnotationAssertionAxiom(self.propIRI, commentannot)

        self.ontology.addTermAxiom(annotaxiom)

    def addSuperproperty(self, parent_id):
        """
        Adds a parent property for this property.

        parent_id: The identifier of the parent property.  Can be either an OWL
            API IRI object or a string containing: a prefix IRI (i.e., a curie,
            such as "owl:Thing"), a full IRI, or an OBO ID (e.g., a string of
            the form "PO:0000003").
        """
        parentIRI = self.ontology.expandIdentifier(parent_id)

        # Get the OWL property object of the parent, making sure that it is
        # actually defined.
        parentprop = self.ontology.getExistingAnnotationProperty(parentIRI)
        if parentprop == None:
            raise RuntimeError('The designated superproperty, ' + str(parent_id)
                    + ', could not be found in the source ontology.')

        # Add the subproperty axiom to the ontology.
        newaxiom = self.df.getOWLSubAnnotationPropertyOfAxiom(self.propobj, parentprop)
        self.ontology.addTermAxiom(newaxiom)
