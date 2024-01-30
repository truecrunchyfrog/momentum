# -*- coding: utf-8 -*-
from django.http import HttpResponse
from django.shortcuts import redirect
from django.core.cache import cache
from django.conf import settings

__author__ = 'vadim'

KEY_PREFIX = "whitelist_ip_"
ACCESS_EXPIRE = 3600

class WhiteListIPMiddleware(object):
    """
    Handles access from world to site
    """

    def process_request(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', None)
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', None)
        key_cache = KEY_PREFIX + ip
        if key_cache in cache:
            cache.set(key_cache, True, ACCESS_EXPIRE)
        elif request.path.startswith('/admin/'):
            if request.user.is_authenticated():
                cache.add(key_cache, True, ACCESS_EXPIRE)
        else:
            IP_ACCESS = getattr(settings, 'IP_ACCESS', [])
            ip_split = ip.split('.')
            if not ip in IP_ACCESS:
                if not '.'.join(ip_split[:-1]) in IP_ACCESS:
                    if not '.'.join(ip_split[:-2]) in IP_ACCESS:
                        if not '.'.join(ip_split[:-3]) in IP_ACCESS:
                            redir = getattr(settings, 'BLOCK_ACCESS_REDIRECT', None)
                            if redir:
                                return redirect(redir)
                            if hasattr(settings, 'BLOCK_ACCESS_TEMPLATE'):
                                from django.shortcuts import render_to_response
                                return render_to_response(getattr(settings, 'BLOCK_ACCESS_TEMPLATE'))
                            return HttpResponse(content="Access denied", status=403)

