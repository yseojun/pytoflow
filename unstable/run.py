import os
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
# import torch.utils.serialization    # it was removed in torch v1.0.0 or higher version.
import math
import PIL
from Network import TOFlow
import matplotlib.pyplot as plt
import sys
import getopt
from scipy import io

import time
# ------------------------------
# I don't know whether you have a GPU.
# torch.cuda.set_device(0)
# Static
model_name = 'interp'                                                       # select model
workplace = '.'

frameFirstName = None
frameSecondName = None
frameOutName = os.path.join(workplace, 'out.png')
gpuID = None

for strOption, strArgument in getopt.getopt(sys.argv[1:], '', [strParameter[2:] + '=' for strParameter in sys.argv[1::2]])[0]:
    if strOption == '--f1':          # first frame
        frameFirstName = strArgument
    elif strOption == '--f2':        # second frame
        frameSecondName = strArgument
    elif strOption == '--o':         # out frame
        frameOutName = strArgument
    elif strOption == '--gpuID':
        gpuID = int(strArgument)
    elif strOption == '--d1':
        flowFirstName = strArgument
    elif strOption == '--d2':
        flowSecondName = strArgument

if frameFirstName == None or frameSecondName == None:
    raise ('Missing [-f1 frameFirstName or -f2 frameSecondName].\nPlease enter the name of two frames.')

if gpuID == None:
    CUDA = False
else:
    CUDA = True
# ------------------------------
# 数据集中的图片长宽都弄成32的倍数了所以这里可以不用这个函数
# 暂时只用于处理batch_size = 1的triple
def Estimate(net, tensorFirst=None, tensorSecond=None, Firstfilename='', Secondfilename='', Firstflowname='', Secondflowname='', cuda_flag=False):
    """
    :param tensorFirst: 弄成FloatTensor格式的frameFirst
    :param tensorSecond: 弄成FloatTensor格式的frameSecond
    :return:
    """
    if Firstfilename and Secondfilename:
        tensorFirst = torch.FloatTensor(np.array(PIL.Image.open(Firstfilename).convert("RGB")).transpose(2, 0, 1).astype(np.float32) * (1.0 / 255.0))
        tensorSecond = torch.FloatTensor(np.array(PIL.Image.open(Secondfilename).convert("RGB")).transpose(2, 0, 1).astype(np.float32) * (1.0 / 255.0))

    mat_file   = io.loadmat(Firstflowname)
#    flowFirst  = mat_file['OutFlowF']
    flowFirst  = mat_file['save_outflowF']
    flowFirst  = torch.from_numpy(flowFirst.astype(np.float32))
    mat_file   = io.loadmat(Secondflowname)
#    flowSecond = mat_file['OutFlowB']
    flowSecond = mat_file['save_outflowB']
    flowSecond = torch.from_numpy(flowSecond.astype(np.float32))

    tensorOutput = torch.FloatTensor()

    # check whether the two frames have the same shape
    assert (tensorFirst.size(1) == tensorSecond.size(1))
    assert (tensorFirst.size(2) == tensorSecond.size(2))

    intWidth = tensorFirst.size(2)
    intHeight = tensorFirst.size(1)

    # assert(intWidth == 448) # remember that there is no guarantee for correctness, comment this line out if you acknowledge this and want to continue
    # assert(intHeight == 256) # remember that there is no guarantee for correctness, comment this line out if you acknowledge this and want to continue

    if cuda_flag == True:
        tensorFirst = tensorFirst.cuda()
        tensorSecond = tensorSecond.cuda()
        tensorOutput = tensorOutput.cuda()
        flowFirst  = flowFirst.cuda()
        flowSecond = flowSecond.cuda()
    # end
    s1 = time.time()

    if True:
        s3 = time.time()
        tensorPreprocessedFirst = tensorFirst.view(1, 3, intHeight, intWidth)
        tensorPreprocessedSecond = tensorSecond.view(1, 3, intHeight, intWidth)
        flowPreprocessedFirst = flowFirst.view(1, 1, intHeight, intWidth)
        flowPreprocessedSecond = flowSecond.view(1, 1, intHeight, intWidth)

        intPreprocessedWidth = int(math.floor(math.ceil(intWidth / 32.0) * 32.0))  # 宽度弄成32的倍数，便于上下采样
        intPreprocessedHeight = int(math.floor(math.ceil(intHeight / 32.0) * 32.0))  # 长度弄成32的倍数，便于上下采样

        tensorPreprocessedFirst = torch.nn.functional.interpolate(input=tensorPreprocessedFirst, size=(
            intPreprocessedHeight, intPreprocessedWidth), mode='bilinear', align_corners=False)
        tensorPreprocessedSecond = torch.nn.functional.interpolate(input=tensorPreprocessedSecond, size=(
            intPreprocessedHeight, intPreprocessedWidth), mode='bilinear', align_corners=False)
        flowPreprocessedFirst = torch.nn.functional.interpolate(input=flowPreprocessedFirst, size=(
            intPreprocessedHeight, intPreprocessedWidth), mode='bilinear', align_corners=False)
        flowPreprocessedSecond = torch.nn.functional.interpolate(input=flowPreprocessedSecond, size=(
            intPreprocessedHeight, intPreprocessedWidth), mode='bilinear', align_corners=False)
        s4 = time.time()

        tensorFlow = torch.nn.functional.interpolate(
            input=net(torch.stack([tensorPreprocessedFirst, tensorPreprocessedSecond], dim=1), 
                      torch.stack([flowPreprocessedFirst, flowPreprocessedSecond], dim=1)), 
                    size=(intHeight, intWidth), mode='bilinear', align_corners=False)

        tensorOutput.resize_(3, intHeight, intWidth).copy_(tensorFlow[0, :, :, :])
        tensorOutput = tensorOutput.permute(1, 2, 0)
    # end
    s2 = time.time()
    if True:
        tensorFirst = tensorFirst.cpu()
        tensorSecond = tensorSecond.cpu()
        tensorOutput = tensorOutput.cpu()
    # end
    print("total time : " + str(s2 - s1) + "s")
    print("temp  time : " + str(s4 - s3) + "s")

    return tensorOutput.detach().numpy()

# ------------------------------
if __name__ == '__main__':
    if CUDA:
        torch.cuda.set_device(gpuID)
    temp_img = np.array(plt.imread(frameFirstName))
    height = temp_img.shape[0]
    width = temp_img.shape[1]

    intPreprocessedWidth = int(math.floor(math.ceil(width / 32.0) * 32.0))  # 宽度弄成32的倍数，便于上下采样
    intPreprocessedHeight = int(math.floor(math.ceil(height / 32.0) * 32.0))  # 长度弄成32的倍数，便于上下采样

    print('Loading TOFlow Net... ', end='')
    net = TOFlow(intPreprocessedHeight, intPreprocessedWidth, task='interp', cuda_flag=CUDA)
    net.load_state_dict(torch.load(os.path.join(workplace, 'toflow_models', model_name + '.pkl')))
    if CUDA:
        net.eval().cuda()
    else:
        net.eval()

    print('Done.')

    # ------------------------------
    # generate(net=net, model_name=model_name, f1name=os.path.join(test_pic_dir, 'im1.png'),
    #         f2name=os.path.join(test_pic_dir, 'im3.png'), fname=outputname)
    print('Processing...')
    predict = Estimate(net, Firstfilename=frameFirstName, Secondfilename=frameSecondName, Firstflowname=flowFirstName, Secondflowname=flowSecondName, cuda_flag=CUDA)
    #print(predict, np.min(predict), np.max(predict))
    plt.imsave(frameOutName, predict)
    print('%s Saved.' % frameOutName)
