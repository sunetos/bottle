# -*- coding: utf-8 -*-
import unittest
import sys, os.path
import bottle
import urllib2
from StringIO import StringIO
import thread
import time
from tools import ServerTestBase
from bottle import tob, touni, tonat

class TestWsgi(ServerTestBase):
    ''' Tests for WSGI functionality, routing and output casting (decorators) '''

    def test_get(self):
        """ WSGI: GET routes"""
        @bottle.route('/')
        def test(): return 'test'
        self.assertStatus(404, '/not/found')
        self.assertStatus(405, '/', post="var=value")
        self.assertBody('test', '/')

    def test_post(self):
        """ WSGI: POST routes"""
        @bottle.route('/', method='POST')
        def test(): return 'test'
        self.assertStatus(404, '/not/found')
        self.assertStatus(405, '/')
        self.assertBody('test', '/', post="var=value")

    def test_headget(self):
        """ WSGI: HEAD routes and GET fallback"""
        @bottle.route('/get')
        def test(): return 'test'
        @bottle.route('/head', method='HEAD')
        def test2(): return 'test'
        # GET -> HEAD
        self.assertStatus(405, '/head')
        # HEAD -> HEAD
        self.assertStatus(200, '/head', method='HEAD')
        self.assertBody('', '/head', method='HEAD')
        # HEAD -> GET
        self.assertStatus(200, '/get', method='HEAD')
        self.assertBody('', '/get', method='HEAD')

    def get304(self):
        """ 304 responses must not return entity headers """
        bad = ('allow', 'content-encoding', 'content-language',
               'content-length', 'content-md5', 'content-range',
               'content-type', 'last-modified') # + c-location, expires?
        for h in bad:
            bottle.response.set_header(h, 'foo')
        bottle.status = 304
        for h, v in bottle.response.headerlist:
            self.assertFalse(h.lower() in bad, "Header %s not deleted" % h)
            

    def test_anymethod(self):
        self.assertStatus(404, '/any')
        @bottle.route('/any', method='ANY')
        def test2(): return 'test'
        self.assertStatus(200, '/any', method='HEAD')
        self.assertBody('test', '/any', method='GET')
        self.assertBody('test', '/any', method='POST')
        self.assertBody('test', '/any', method='DELETE')
        @bottle.route('/any', method='GET')
        def test2(): return 'test2'
        self.assertBody('test2', '/any', method='GET')
        @bottle.route('/any', method='POST')
        def test2(): return 'test3'
        self.assertBody('test3', '/any', method='POST')
        self.assertBody('test', '/any', method='DELETE')

    def test_500(self):
        """ WSGI: Exceptions within handler code (HTTP 500) """
        @bottle.route('/')
        def test(): return 1/0
        self.assertStatus(500, '/')

    def test_503(self):
        """ WSGI: Server stopped (HTTP 503) """
        @bottle.route('/')
        def test(): return 'bla'
        self.assertStatus(200, '/')
        bottle.app().serve = False
        self.assertStatus(503, '/')

    def test_401(self):
        """ WSGI: abort(401, '') (HTTP 401) """
        @bottle.route('/')
        def test(): bottle.abort(401)
        self.assertStatus(401,'/')
        @bottle.error(401)
        def err(e):
            bottle.response.status = 200
            return str(type(e))
        self.assertStatus(200,'/')
        self.assertBody("<class 'bottle.HTTPError'>",'/')

    def test_303(self):
        """ WSGI: redirect (HTTP 303) """
        @bottle.route('/')
        def test(): bottle.redirect('/yes')
        self.assertStatus(303, '/')
        self.assertHeader('Location', 'http://127.0.0.1/yes', '/')

    def test_generator_callback(self):
        @bottle.route('/yield')
        def test():
            bottle.response.headers['Test-Header'] = 'test'
            yield 'foo'
        @bottle.route('/yield_nothing')
        def test2():
            yield
            bottle.response.headers['Test-Header'] = 'test'
        self.assertBody('foo', '/yield')
        self.assertHeader('Test-Header', 'test', '/yield')
        self.assertBody('', '/yield_nothing')
        self.assertHeader('Test-Header', 'test', '/yield_nothing')

    def test_cookie(self):
        """ WSGI: Cookies """
        @bottle.route('/cookie')
        def test():
            bottle.response.COOKIES['a']="a"
            bottle.response.set_cookie('b', 'b')
            bottle.response.set_cookie('c', 'c', path='/')
            return 'hello'
        try:
            c = self.urlopen('/cookie')['header'].get_all('Set-Cookie', '')
        except:
            c = self.urlopen('/cookie')['header'].get('Set-Cookie', '').split(',')
            c = [x.strip() for x in c]
        self.assertTrue('a=a' in c)
        self.assertTrue('b=b' in c)
        self.assertTrue('c=c; Path=/' in c)

class TestRouteDecorator(ServerTestBase):
    def test_decorators(self):
        def foo(): return bottle.request.method
        bottle.get('/')(foo)
        bottle.post('/')(foo)
        bottle.put('/')(foo)
        bottle.delete('/')(foo)
        for verb in 'GET POST PUT DELETE'.split():
            self.assertBody(verb, '/', method=verb)

    def test_single_path(self):
        @bottle.route('/a')
        def test(): return 'ok'
        self.assertBody('ok', '/a')
        self.assertStatus(404, '/b')

    def test_path_list(self):
        @bottle.route(['/a','/b'])
        def test(): return 'ok'
        self.assertBody('ok', '/a')
        self.assertBody('ok', '/b')
        self.assertStatus(404, '/c')

    def test_no_path(self):
        @bottle.route()
        def test(x=5): return str(x)
        self.assertBody('5', '/test')
        self.assertBody('6', '/test/6')

    def test_no_params_at_all(self):
        @bottle.route
        def test(x=5): return str(x)
        self.assertBody('5', '/test')
        self.assertBody('6', '/test/6')

    def test_method(self):
        @bottle.route(method='gEt')
        def test(): return 'ok'
        self.assertBody('ok', '/test', method='GET')
        self.assertStatus(200, '/test', method='HEAD')
        self.assertStatus(405, '/test', method='PUT')

    def test_method_list(self):
        @bottle.route(method=['GET','post'])
        def test(): return 'ok'
        self.assertBody('ok', '/test', method='GET')
        self.assertBody('ok', '/test', method='POST')
        self.assertStatus(405, '/test', method='PUT')

    def test_decorate(self):
        def revdec(func):
            def wrapper(*a, **ka):
                return reversed(func(*a, **ka))
            return wrapper

        @bottle.route('/nodec')
        @bottle.route('/dec', decorate=revdec)
        def test(): return '1', '2'
        self.assertBody('21', '/dec')
        self.assertBody('12', '/nodec')

    def test_decorate_list(self):
        def revdec(func):
            def wrapper(*a, **ka):
                return reversed(func(*a, **ka))
            return wrapper
        def titledec(func):
            def wrapper(*a, **ka):
                return ''.join(func(*a, **ka)).title()
            return wrapper

        @bottle.route('/revtitle', decorate=[revdec, titledec])
        @bottle.route('/titlerev', decorate=[titledec, revdec])
        def test(): return 'a', 'b', 'c'
        self.assertBody('cbA', '/revtitle')
        self.assertBody('Cba', '/titlerev')

    def test_hooks(self):
        @bottle.route()
        def test():
            return bottle.request.environ.get('hooktest','nohooks')
        @bottle.hook('before_request')
        def hook():
            bottle.request.environ['hooktest'] = 'before'
        @bottle.hook('after_request')
        def hook():
            bottle.response.headers['X-Hook'] = 'after'
        self.assertBody('before', '/test')
        self.assertHeader('X-Hook', 'after', '/test')

    def test_no_hooks(self):
        @bottle.route(no_hooks=True)
        def test():
            return 'nohooks'
        bottle.hook('before_request')(lambda: 1/0)
        bottle.hook('after_request')(lambda: 1/0)
        self.assertBody('nohooks', '/test')

    def test_template(self):
        @bottle.route(template='test {{a}} {{b}}')
        def test(): return dict(a=5, b=6)
        self.assertBody('test 5 6', '/test')

    def test_template_opts(self):
        @bottle.route(template='test {{a}} {{b}}', template_opts={'b': 6})
        def test(): return dict(a=5)
        self.assertBody('test 5 6', '/test')

    def test_static(self):
        @bottle.route('/:foo', static=True)
        def test(): return 'ok'
        self.assertBody('ok', '/:foo')

    def test_name(self):
        @bottle.route(name='foo')
        def test(x=5): return 'ok'
        self.assertEquals('/test/6', bottle.url('foo', x=6))

    def test_callback(self):
        def test(x=5): return str(x)
        rv = bottle.route(callback=test)
        self.assertBody('5', '/test')
        self.assertBody('6', '/test/6')
        self.assertEqual(rv, test)




class TestDecorators(ServerTestBase):
    ''' Tests Decorators '''

    def test_view(self):
        """ WSGI: Test view-decorator (should override autojson) """
        @bottle.route('/tpl')
        @bottle.view('stpl_t2main')
        def test():
            return dict(content='1234')
        result = '+base+\n+main+\n!1234!\n+include+\n-main-\n+include+\n-base-\n'
        self.assertHeader('Content-Type', 'text/html; charset=UTF-8', '/tpl')
        self.assertBody(result, '/tpl')

    def test_view_error(self):
        """ WSGI: Test if view-decorator reacts on non-dict return values correctly."""
        @bottle.route('/tpl')
        @bottle.view('stpl_t2main')
        def test():
            return bottle.HTTPError(401, 'The cake is a lie!')
        self.assertInBody('The cake is a lie!', '/tpl')
        self.assertInBody('401: Unauthorized', '/tpl')
        self.assertStatus(401, '/tpl')

    def test_validate(self):
        """ WSGI: Test validate-decorator"""
        @bottle.route('/:var')
        @bottle.route('/')
        @bottle.validate(var=int)
        def test(var): return 'x' * var
        self.assertStatus(403,'/noint')
        self.assertStatus(403,'/')
        self.assertStatus(200,'/5')
        self.assertBody('xxx', '/3')

    def test_truncate_body(self):
        """ WSGI: Some HTTP status codes must not be used with a response-body """
        @bottle.route('/test/:code')
        def test(code):
            bottle.response.status = int(code)
            return 'Some body content'
        self.assertBody('Some body content', '/test/200')
        self.assertBody('', '/test/100')
        self.assertBody('', '/test/101')
        self.assertBody('', '/test/204')
        self.assertBody('', '/test/304')

    def test_routebuild(self):
        """ WSGI: Test route builder """
        def foo(): pass
        bottle.route('/a/:b/c', name='named')(foo)
        bottle.request.environ['SCRIPT_NAME'] = ''
        self.assertEqual('/a/xxx/c', bottle.url('named', b='xxx'))
        self.assertEqual('/a/xxx/c', bottle.app().get_url('named', b='xxx'))
        bottle.request.environ['SCRIPT_NAME'] = '/app'
        self.assertEqual('/app/a/xxx/c', bottle.url('named', b='xxx'))
        bottle.request.environ['SCRIPT_NAME'] = '/app/'
        self.assertEqual('/app/a/xxx/c', bottle.url('named', b='xxx'))
        bottle.request.environ['SCRIPT_NAME'] = 'app/'
        self.assertEqual('/app/a/xxx/c', bottle.url('named', b='xxx'))

    def test_autoroute(self):
        app = bottle.Bottle()
        def a(): pass
        def b(x): pass
        def c(x, y): pass
        def d(x, y=5): pass
        def e(x=5, y=6): pass
        self.assertEqual(['/a'],list(bottle.yieldroutes(a)))
        self.assertEqual(['/b/:x'],list(bottle.yieldroutes(b)))
        self.assertEqual(['/c/:x/:y'],list(bottle.yieldroutes(c)))
        self.assertEqual(['/d/:x','/d/:x/:y'],list(bottle.yieldroutes(d)))
        self.assertEqual(['/e','/e/:x','/e/:x/:y'],list(bottle.yieldroutes(e)))


     
class TestAppShortcuts(ServerTestBase):
    def setUp(self):
        ServerTestBase.setUp(self)
    
    def assertWraps(self, test, other):
        self.assertEqual(test.__doc__, other.__doc__)
    
    def test_module_shortcuts(self):
        for name in '''route get post put delete error mount
                       hook install uninstall'''.split():
            short = getattr(bottle, name)
            original = getattr(bottle.app(), name)            
            self.assertWraps(short, original)

    def test_module_shortcuts_with_different_name(self):
        self.assertWraps(bottle.url, bottle.app().get_url)



class TestAppMounting(ServerTestBase):
    def setUp(self):
        ServerTestBase.setUp(self)
        self.subapp = bottle.Bottle()
    
    def test_basicmounting(self):
        bottle.app().mount(self.subapp, '/test')
        self.assertStatus(404, '/')
        self.assertStatus(404, '/test')
        self.assertStatus(404, '/test/')
        self.assertStatus(404, '/test/test/bar')
        @self.subapp.route('/')
        @self.subapp.route('/test/:test')
        def test(test='foo'):
            return test
        self.assertStatus(404, '/')
        self.assertStatus(404, '/test')
        self.assertStatus(200, '/test/')
        self.assertBody('foo', '/test/')
        self.assertStatus(200, '/test/test/bar')
        self.assertBody('bar', '/test/test/bar')


    
if __name__ == '__main__': #pragma: no cover
    unittest.main()
