from django import template

register = template.Library()

@register.filter
def get_item(sequence, position):
    try:
        return sequence[position]
    except IndexError:
        return None
    

@register.filter(name='get_submission')
def get_submission(dictionary, key):
    if dictionary and isinstance(dictionary, dict):
        return dictionary.get(str(key) if isinstance(key, str) else key)
    return None