import os
import numpy as np
import nibabel as nib
import matplotlib.pyplot as plt
from scipy.ndimage import affine_transform, zoom
import datetime

image_path = 'bv_body_data/predict/'
data_path = 'img_'
label_path = 'bv_body'
appendix_str = '.nii'

def loadnii(x, xout, yout, zout, mode='pad', mask=False):

	"""
	load the nii image and label into np array 
	input:
		x: int index of the image to read
	return: 
		tuple of (image, label)
	"""

	data_file = os.path.join(image_path, data_path + str(x) + appendix_str)
	label_file = os.path.join(image_path, label_path + str(x)+ appendix_str)

	data = ((nib.load(data_file)).get_fdata()).astype(np.float32)
	label = ((nib.load(label_file)).get_fdata()).astype(np.float32)/2

	if mode == 'pad':

		data = zero_padding(data, xout, yout, zout)
		label = zero_padding(label, xout, yout, zout)

	else:
		x, y, z = data.shape
		#scale the image
		data = zoom(data, zoom=(xout/x, yout/y, zout/z))
		label = zoom(label, zoom=(xout/x, yout/y, zout/z))

	data = data.reshape(1, *data.shape)
	label= label.reshape(1, *label.shape)
	
	return (data, label)

def savenii(img, PATH): 
	timestamp = datetime.datetime.now()
	filename = PATH + str(timestamp) + appendix_str
	array_img = nib.Nifti1Image(img, np.eye(4))
	nib.save(array_img, filename)

def getniishape(x):

	"""
	get the upperbound shape of image array
	input:
		x: number of image
	return: 
		array of tuple of (max x, max y, max z)
	"""
	label_file = os.path.join(image_path, label_path + str(x)+ appendix_str)
	label = ((nib.load(label_file)).get_fdata()).astype(np.float32)/2

	return label.shape

def zero_padding (img, target_x, target_y, target_z):
	"""
	reshaping the img to desirable shape through zero pad or crop
	Args:
		img: input 3d nii array
		target_x: target shape x
		target_y: target shape y
		target_z: target shape z
	Ret:
		img: reshaped 3d nii array
	"""

	padx = (target_x-img.shape[0])//2
	pady = (target_y-img.shape[1])//2
	padz = (target_z-img.shape[2])//2

	if padx<0:
		img = img[-padx:padx,:,:]
	else:
		img = np.pad (img, ((padx,padx),(0, 0),(0, 0)), \
			mode='constant', constant_values=((0,0),(0,0),(0,0)))

	if pady <0:
		img = img[:,-pady:pady,:]
	else:
		img = np.pad (img, ((0,0),(pady, pady),(0, 0)), \
			mode='constant', constant_values=((0,0),(0,0),(0,0)))

	if padz <0:
		img = img[:,:,-padz:padz]
	else:
		img = np.pad (img, ((0,0),(0, 0),(padz, padz)), \
			mode='constant', constant_values=((0,0),(0,0),(0,0)))

	return img

def show_image(img, label, indice=-1):

	"""
	show a slice of image with label at certain indice
	input:
		img: input image (1, X, Y, X)
		label: input label
		indice: cutting indice
	return: 
		None
	"""

	if indice ==-1:
		indice = img.shape[1]//2

	fig, ax = plt.subplots(1,2)

	ax[0].imshow(img[0][indice], cmap='gray')
	ax[1].imshow(label[0][indice], cmap='gray')
	plt.show()

def show_image_4(img, label, indice=-1):
	"""
	show a slice of image with label at certain indice
	input:
		img: input image (1, X, Y, X)
		label: input label after one hot coding
		indice: cutting indice
	return: 
		None
	"""
	if indice ==-1:
		indice = img.shape[1]//2

	fig, ax = plt.subplots(2,2)

	ax[0][0].imshow(img[0][indice], cmap='gray')
	ax[0][1].imshow(label[0][indice], cmap='gray')
	ax[1][0].imshow(label[1][indice], cmap='gray')
	ax[1][1].imshow(label[2][indice], cmap='gray')
	plt.show()

def show_batch_image(img, label, batchsize, indice=-1, level=4):
	'''
	show batch of Tensor as image

	'''
	img = img.numpy()
	label = label.numpy()

	if level==4:
		for i in range(batchsize):
			show_image_4(img[i], label[i], indice)

	elif level ==2:
		for i in range(batchsize):
			show_image(img[i], label[i], indice)
	else:
		pass

def loadallnii(x, bad_index, target_x=-1, target_y=-1, target_z=-1, verbose=False):

	"""
	DEP!
	load all nii image and label into np array
	input:
		x: number of image
		traget_shape: if preknown the target shape, else calculate
		verbose: whether print the slicing out
	return: 
		tuple of array (max x, max y, max z)
	"""

	target_shape = None

	if target_x < 0:
		target_shape = getniishape(x)
	else:
		target_shape = (target_x, target_y, target_z)

	xx = x - bad_index.shape[0]

	image = np.zeros((xx, 1, *target_shape), dtype=np.float32) # single channel image
	label = np.zeros((xx, 1, *target_shape), dtype=np.float32) # triple channel label

	j = 0
	for i in range(x):

		if np.isin(i, bad_index):
			pass
		else:
			temp_image, temp_label = loadnii(i, target_x, target_y, target_z)
			current_shape = temp_image.shape
			padx = (target_shape[0]-current_shape[0])//2

			image[j] = zero_padding(temp_image, *target_shape)
			label[j] = zero_padding(temp_label, *target_shape)/2

			print('image index loaded: ' + str(i))

			if verbose:
				show_image(image[j], label[j] , 90+padx)

			else:
				pass

			j += 1

	return (image, label)
