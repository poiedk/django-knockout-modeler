import cgi

from django.db import models
from django.forms.models import model_to_dict
from django.template.loader import render_to_string

try:
    import simplejson as json
except ImportError as e:
    import json
import datetime

import logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def get_fields(model):
    """
    Returns a Model's knockout_fields,
    or the default set of field names.
    """

    try:
        if hasattr(model, "knockout_fields"):
            fields = model.knockout_fields()
        else:
            try:
                fields = list(model_to_dict(model).keys())
            except Exception as e:
                fields = model._meta.get_fields()
        return fields

    # Crash proofing
    except Exception as e:
        logger.exception(e)
        return []


def get_object_data(obj, fields, safe):
    """
    Given an object and a list of fields, recursively build an object for serialization.

    Returns a dictionary.
    """

    temp_dict = dict()
    for field in fields:

        try:
            attribute = getattr(obj, str(field))
            if isinstance(attribute, list) and all([isinstance(item, models.Model) for item in attribute]):
                temp_dict[field] = []
                for item in attribute:
                    temp_dict[field].append(get_object_data(item, get_fields(item), safe))  # Recur
            elif isinstance(attribute, models.Model):
                attribute_fields = get_fields(attribute)
                object_data = get_object_data(attribute, attribute_fields, safe)  # Recur
                temp_dict[field] = object_data
            else:
                if not safe:
                    if isinstance(attribute, str):
                        attribute = cgi.escape(attribute)
                temp_dict[field] = attribute

        except Exception as e:
            logger.info("Unable to get attribute.")
            logger.error(e)
            continue

    return temp_dict


def ko_model(model, field_names=None, data=None):
    """
    Given a model, returns the Knockout Model and the Knockout ViewModel.
    Takes optional field names and data.
    """

    try:
        if isinstance(model, str):
            modelName = model
        else:
            modelName = model.__class__.__name__

        if field_names:
            fields = field_names
        else:
            fields = get_fields(model)

        if hasattr(model, "comparator"):
            comparator = str(model.comparator())
        else:
            comparator = 'id'

        modelViewString = render_to_string(
            "knockout_modeler/model.js",
            {'modelName': modelName, 'fields': fields, 'data': data, 'comparator': comparator}
        )

        return modelViewString
    except Exception as e:
        logger.exception(e)
        return ''


def ko_bindings(model):
    """
    Given a model, returns the Knockout data bindings.
    """

    try:
        if isinstance(model, str):
            modelName = model
        else:
            modelName = model.__class__.__name__

        modelBindingsString = "ko.applyBindings(new " + modelName + "ViewModel(), $('#" + modelName.lower() + "s')[0]);"
        return modelBindingsString

    except Exception as e:
        logger.error(e)
        return ''


def ko_json(queryset, field_names=None, name=None, safe=False):
    """
    Given a QuerySet, return just the serialized representation
    based on the knockout_fields. Useful for middleware/APIs.

    Convenience method around ko_data.

    """
    return ko_data(queryset, field_names, name, safe, return_json=True)


def ko_data(queryset, field_names=None, name=None, safe=False, return_json=False):
    """
    Given a QuerySet, return just the serialized representation
    based on the knockout_fields as JavaScript.

    """

    try:
        try:
            # Get an inital instance of the QS.
            queryset_instance = queryset[0]
        except TypeError as e:
            # We are being passed an object rather than a QuerySet.
            # That's naughty, but we'll survive.
            queryset_instance = queryset
            queryset = [queryset]
        except IndexError as e:
            if not isinstance(queryset, list):
                # This is an empty QS - get the model directly.
                queryset_instance = queryset.model
            else:
                # We have been given an empty list.
                # Return nothing.
                return '[]'

        modelName = queryset_instance.__class__.__name__
        modelNameData = []

        if field_names is not None:
            fields = field_names
        else:
            fields = get_fields(queryset_instance)

        for obj in queryset:
            object_data = get_object_data(obj, fields, safe)
            modelNameData.append(object_data)

        if name:
            modelNameString = name
        else:
            modelNameString = modelName + "Data"

        dthandler = lambda obj: obj.isoformat() if isinstance(obj, (datetime.date, datetime.datetime)) else None
        dumped_json = json.dumps(modelNameData, default=dthandler)

        if return_json:
            return dumped_json
        return "var " + modelNameString + " = " + dumped_json + ';'
    except Exception as e:
        logger.exception(e)
        return '[]'


def ko(queryset, field_names=None):
    """
    Converts a Django QuerySet into a complete Knockout implementation.
    """

    try:
        koDataString = ko_data(queryset, field_names)
        koModelString = ko_model(queryset[0].__class__.__name__, field_names, data=True)
        koBindingsString = ko_bindings(queryset[0])

        koString = koDataString + '\n' + koModelString + '\n' + koBindingsString

        return koString
    except Exception as e:
        logger.error(e)
        return ''
