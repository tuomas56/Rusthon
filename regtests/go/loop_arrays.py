'''
array loop
'''

def main():

	a = [1,2,3]
	y = 0
	for x in a:
		y += x
	TestError( y==6 )

	z = ''
	arr = ['a', 'b', 'c']
	for v in arr:
		z += v
	TestError( z == 'abc' )

	b = 0
	for i in range(10):
		b += 1
	TestError( b == 10 )

	b2 = 0
	for i in range(5, 10):
		b2 += 1
	TestError( b2 == 5 )


	c = ''
	d = 0
	for i,v in enumerate(arr):
		c += v
		d += i
	TestError( c == 'abc' )

	e = 0
	for i in range( len(arr) ):
		e += 1
	TestError( e == 3 )

	s = a[:2]
	#print('len of s:')
	#print(len(s))
	TestError( len(s)==2 )

	s2 = a[2:]
	#print('len of s2:')
	#print(len(s2))
	#print(s2[0])
	TestError( len(s2)==1 )

	#e = 0
	#for i in s:
	#	e += i
	#TestError( e == 3 )
		