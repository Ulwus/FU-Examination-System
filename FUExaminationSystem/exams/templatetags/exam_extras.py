from django import template

register = template.Library()

@register.filter
def get_item(sequence, position):
    try:
        return sequence[position]
    except IndexError:
        return None