Lua Translator
--------------

experimental!

This works by transforming all method calls to plain functions `Class_Method`,
see `TransformSuperCalls` here: [astutils.md](astutils.md)

Some dynamic parts of python are supported using `__get__`, defined here:
[lua_builtins.py](runtime/lua_builtins.py)

note Bit-operations require LuaJIT


```python

class LuaGenerator( JSGenerator ):

	def __init__(self, source=None, requirejs=False, insert_runtime=False):
		JSGenerator.__init__(self, source=source, requirejs=False, insert_runtime=False)
		self._classes = dict()
		self._class_props = dict()
		self._lua = True

	def visit_BinOp(self, node):
		left = self.visit(node.left)
		op = self.visit(node.op)
		right = self.visit(node.right)
		if op == '&':
			return '(__bitops__.band(%s, %s))' %(left, right)
		elif op == '|':
			return '(__bitops__.bor(%s, %s))' %(left, right)
		elif op == '^':
			return '(__bitops__.bxor(%s, %s))' %(left, right)
		elif op == '<<':
			return '(__bitops__.lshift(%s, %s))' %(left, right)
		elif op == '>>':
			return '(__bitops__.rshift(%s, %s))' %(left, right)
		else:
			return '(%s %s %s)' % (left, op, right)


	def _visit_subscript_ellipsis(self, node):
		name = self.visit(node.value)
		return '%s.__wrapped__' %name

	def visit_Name(self, node):
		if node.id == 'None':
			return 'nil'
		elif node.id == 'True':
			return 'true'
		elif node.id == 'False':
			return 'false'
		elif node.id == 'null':
			return 'nil'
		return node.id

	def visit_And(self, node):
		return ' and '

	def visit_Or(self, node):
		return ' or '

	def visit_Not(self, node):
		return ' not '

	def visit_IsNot(self, node):
		return '~='

	def visit_NotEq(self, node):
		return '~='

	def visit_Is(self, node):
		return '=='

	def visit_Subscript(self, node):
		if isinstance(node.slice, ast.Ellipsis):
			return self._visit_subscript_ellipsis( node )
		else:
			return '%s[%s]' % (self.visit(node.value), self.visit(node.slice))

	def _visit_call_helper_JSObject(self, node):
		if node.keywords:
			kwargs = map(self.visit, node.keywords)
			f = lambda x: '%s = %s' % (x[0], x[1])
			out = ', '.join(map(f, kwargs))
			return '{%s}' % out
		else:
			return '{}'

	def _visit_call_helper_JSArray(self, node):
		if node.args:
			args = map(self.visit, node.args)
			out = ', '.join(args)
			return '{%s}' % out
		else:
			return '{}'

	def _visit_call_helper_var(self, node):
		args = [ self.visit(a) for a in node.args ]
		if self._function_stack:
			fnode = self._function_stack[-1]
			rem = []
			for arg in args:
				if arg in fnode._local_vars:
					rem.append( arg )
				else:
					fnode._local_vars.add( arg )
			for arg in rem:
				args.remove( arg )

		if args:
			out = ', '.join(args)
			return 'local %s' % out
		else:
			return ''

	def _inline_code_helper(self, s):
		return s

	def visit_While(self, node):
		body = [ 'while %s do' %self.visit(node.test)]
		self.push()
		for line in list( map(self.visit, node.body) ):
			body.append( self.indent()+line )
		self.pull()
		body.append( self.indent() + 'end' )
		return '\n'.join( body )



	def visit_Pass(self, node):
		return '--pass--'

	def visit_If(self, node):
		out = []
		out.append( 'if %s then' %self.visit(node.test) )
		self.push()

		for line in list(map(self.visit, node.body)):
			out.append( self.indent() + line )

		orelse = []
		for line in list(map(self.visit, node.orelse)):
			orelse.append( self.indent() + line )

		self.pull()

		if orelse:
			out.append( self.indent() + 'else')
			out.extend( orelse )

		out.append( self.indent() + 'end')


		return '\n'.join( out )


	def visit_List(self, node):
		## note, arrays in lua start at index 1, not zero!
		return '{%s}' % ', '.join(map(self.visit, node.elts))

	def visit_Dict(self, node):
		a = []
		for i in range( len(node.keys) ):
			k = self.visit( node.keys[ i ] )
			v = self.visit( node.values[i] )
			a.append( '%s=%s'%(k,v) )
		b = ','.join( a )
		return '{%s}' %b

	def visit_ClassDef(self, node):
		raise NotImplementedError

	def visit_For(self, node):
		if isinstance(node.target, ast.Name):
			a = ['for __i,%s in pairs(%s) do' %(self.visit(node.target), self.visit(node.iter))]
		elif isinstance(node.target, ast.List):
			x = ','.join([self.visit(elt) for elt in node.target.elts])
			a = ['for %s in %s do' %(x, self.visit(node.iter))]
		else:
			raise SyntaxError( node.target )

		for n in node.body:
			a.append( self.visit(n) )
		a.append('end')
		return '\n'.join(a)

	def visit_Expr(self, node):
		return self.visit(node.value)


	def visit_Print(self, node):
		args = [self.visit(e) for e in node.values]
		return 'print(%s)' % ', '.join(args)


	def visit_Return(self, node):
		if isinstance(node.value, ast.Tuple):
			return 'return __get__(list,"__call__")({}, {pointer={%s}, length=%s});' % (', '.join([self.visit(e) for e in node.value.elts]), len(node.value.elts))
		if node.value:
			return 'return %s;' % self.visit(node.value)
		return 'return nil;'

	def visit_Assign(self, node):
		assert len(node.targets) == 1
		target = node.targets[0]
		if isinstance(target, ast.Tuple):
			elts = [self.visit(e) for e in target.elts]
			return '%s = %s' % (','.join(elts), self.visit(node.value))

		else:
			target = self.visit(target)
			value = self.visit(node.value)
			code = '%s = %s;' % (target, value)
			return code

	def _visit_function(self, node):
		getter = False
		setter = False
		klass = None
		for decor in node.decorator_list:
			if isinstance(decor, ast.Name) and decor.id == 'property':
				getter = True
			elif isinstance(decor, ast.Attribute) and isinstance(decor.value, ast.Name) and decor.attr == 'setter':
				setter = True
			elif isinstance(decor, ast.Call) and isinstance(decor.func, ast.Name) and decor.func.id == '__typedef__':
				pass
			elif isinstance(decor, ast.Call) and isinstance(decor.func, ast.Name) and decor.func.id == '__prototype__':
				assert len(decor.args)==1
				klass = decor.args[0].id

		args = []  #self.visit(node.args)
		oargs = []
		offset = len(node.args.args) - len(node.args.defaults)
		varargs = False
		varargs_name = None
		for i, arg in enumerate(node.args.args):
			a = arg.id
			dindex = i - offset

			if dindex >= 0 and node.args.defaults:
				default_value = self.visit( node.args.defaults[dindex] )
				oargs.append( '%s=%s' %(a, default_value) )
			else:
				args.append( a )

		if oargs:
			args.extend( ','.join(oargs) )

		buffer = self.indent()
		if hasattr(node,'_prefix'): buffer += node._prefix + ' '

		#if getter:
		#	buffer += 'get %s {\n' % node.name
		#elif setter:
		#	buffer += 'set %s(%s) {\n' % (node.name, ', '.join(args))
		#else:
		if klass:
			buffer += '%s.%s = function(%s)\n' % (klass, node.name, ', '.join(args))
		else:
			buffer += '%s = function(%s)\n' % (node.name, ', '.join(args))
		self.push()

		#if varargs:
		#	buffer += 'var %s = new list([]);\n' %varargs_name
		#	for i,n in enumerate(varargs):
		#		buffer += 'if (%s != null) %s.append(%s);\n' %(n, varargs_name, n)

		body = list()
		for child in node.body:
			if isinstance(child, ast.Str):
				continue
			elif isinstance(child, ast.Expr) and isinstance(child.value, ast.Str):
				continue
			else:
				body.append( self.indent() + self.visit(child) )

		body.append( '' )
		buffer += '\n'.join(body)
		self.pull()
		buffer += self.indent() + 'end'

		return buffer


	def _visit_call_helper_instanceof(self, node):
		raise NotImplementedError

	def visit_Raise(self, node):
		return 'error(%s)' % self.visit(node.type)

	def visit_TryExcept(self, node):
		out = ['__try__ = function()']
		self.push()
		for n in node.body:
			out.append( self.indent() + self.visit(n) )
		self.pull()
		out.append( self.indent() + 'end' )

		out.append( self.indent() + 'local __ok__, __exception__ = pcall(__try__)' )
		out.append( self.indent() + 'if not __ok__ then' )
		self.push()
		for n in node.handlers:
			out.append( self.visit(n) )
		self.pull()
		out.append( self.indent() + 'end' )
		return '\n'.join( out )

	def visit_ExceptHandler(self, node):
		## TODO check exception type
		out = []
		if node.type:
			out.append( self.indent() + '--exception: %s' %self.visit(node.type) )
		for n in node.body:
			out.append( self.indent() + self.visit(n) )

		return '\n'.join(out)

def translate_to_lua(script):
	#raise SyntaxError(script)
	tree = ast.parse(script)
	return LuaGenerator( source=script ).visit(tree)


```