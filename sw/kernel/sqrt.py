import torch
from UnarySim.sw.stream.gen import RNG
from UnarySim.sw.stream.shuffle import Bi2Uni, Uni2Bi
from UnarySim.sw.stream.shuffle_int import SkewedSyncInt
from UnarySim.sw.kernel.shiftreg import ShiftReg
from UnarySim.sw.kernel.jkff import JKFF
from UnarySim.sw.kernel.div import CORDIV_kernel, UnaryDiv
import math

class UnarySqrt(torch.nn.Module):
    """
    this module is for unary square root, including iscbdiv-based and jkdiv-based.
    """
    def __init__(self, 
                 mode="bipolar", 
                 jk_trace=True, 
                 depth_kernel=1, 
                 rng="Sobol", 
                 rng_dim=4, 
                 emit=True, 
                 depth_emit=3, 
                 depth_sync=2, # indicate the maximum accumulator depth
                 stype=torch.float):
        super(UnarySqrt, self).__init__()
        
        assert math.ceil(math.log2(depth_kernel)) == math.floor(math.log2(depth_kernel)) , "Input depth_kernel needs to be power of 2."
        assert depth_emit<=31 , "Input depth_emit needs to less than 31."
        self.mode = mode
        self.stype = stype
        self.jk_trace = jk_trace
        self.emit = emit
        if emit is True:
            self.trace_emit = torch.nn.Parameter(torch.zeros(1).type(torch.int), requires_grad=False)
            self.emit_acc_max = torch.nn.Parameter(torch.zeros(1).fill_(2**depth_emit-1).type(torch.int), requires_grad=False)
            self.emit_acc = torch.nn.Parameter(torch.zeros(1).type(torch.int), requires_grad=False)
            
            # following modules use skewedsyncint in UnaryDiv, and can output digit stream
            self.ssyncint = SkewedSyncInt(depth=depth_sync, stype=torch.int, buftype=torch.float)
            self.cordiv_kernel_emit = CORDIV_kernel(depth=depth_kernel, rng=rng, rng_dim=rng_dim, stype=torch.int)
            
            # follow module uses skewedsync in UnaryDiv, and can only output bit stream
            # self.unidiv_emit = UnaryDiv(depth_abs=4, 
            #                             depth_kernel=depth, 
            #                             depth_sync=2, 
            #                             shiftreg_abs=False, 
            #                             mode="unipolar", 
            #                             rng=rng, 
            #                             rng_dim=rng_dim, 
            #                             stype=torch.int, 
            #                             buftype=torch.float)
            
            if mode is "bipolar":
                self.bi2uni_emit = Bi2Uni(stype=torch.int)
                self.uni2bi_emit = Uni2Bi(stype=torch.int)
        else:
            self.trace = torch.nn.Parameter(torch.zeros(1).type(torch.int8), requires_grad=False)
            if mode is "bipolar":
                self.bi2uni = Bi2Uni(stype=torch.int8)
            if jk_trace is True:
                self.jkff = JKFF(stype=torch.int8)
            else:
                self.cordiv_kernel = CORDIV_kernel(depth=depth_kernel, rng=rng, rng_dim=rng_dim, stype=torch.int8)
                self.dff = torch.nn.Parameter(torch.zeros(1).type(torch.int8), requires_grad=False)
        
    def bipolar_trace(self, output):
        # P_trace = (P_out*2-1)/((P_out*2-1)+1)
        out = self.bi2uni(output)
        trace = self.unipolar_trace(out)
        return trace
    
    def unipolar_trace(self, output):
        # P_trace = P_out/(P_out+1)
        if self.jk_trace is True:
            # use JKFF
            trace = self.jkff(output, torch.ones_like(output))
        else:
            # use UnaryDiv
            dividend = (1 - self.dff) & output
            divisor = self.dff + dividend
            
            # use historic quotient as trace
            # trace = self.cordiv_kernel.historic_q[0]
            # _ = self.cordiv_kernel(dividend, divisor)
            
            # use actual quotient as trace
            trace = self.cordiv_kernel(dividend, divisor)
            
            self.dff.data = 1 - self.dff
        return trace
    
    def unipolar_trace_emit(self, output):
        # P_trace = (1-P_out)/P_out
        # use UnaryDiv
        dividend = 1 - output
        divisor = output
        
        # for using skewedsyncint
        dividend_sync, divisor_sync = self.ssyncint(dividend, divisor)
        
        # use cordiv output
        trace_emit = self.cordiv_kernel_emit(dividend_sync, divisor_sync)
        
        # use cordiv historical output
        # _ = self.cordiv_kernel_emit(dividend_sync, divisor_sync)
        # trace_emit = self.cordiv_kernel_emit.historic_q[0]
        
        self.emit_acc.data = self.emit_acc.add(trace_emit)
        
        return trace_emit

    def forward(self, input):
        if self.emit is True:
            if self.mode is "bipolar":
                in_bs = self.bi2uni_emit(input)
                
                emit_acc_gt_0 = torch.gt(self.emit_acc, 0).type(torch.int)
                # only when emit_acc is greater than 0 and input is 0, emitting is enabled.
                emit_en = (1 - in_bs.type(torch.int)) & emit_acc_gt_0
                out_bs = in_bs.type(torch.int) + emit_en
                # update emit_acc based on output
                dontcare = self.unipolar_trace_emit(out_bs)
                # update emit_acc based on emit_en
                self.emit_acc.data = self.emit_acc.sub(emit_en).clamp(0, self.emit_acc_max.item())
                
                output = self.uni2bi_emit(out_bs)
            else:
                emit_acc_gt_0 = torch.gt(self.emit_acc, 0).type(torch.int)
                # only when emit_acc is greater than 0 and input is 0, emitting is enabled.
                emit_en = (1 - input.type(torch.int)) & emit_acc_gt_0
                output = input.type(torch.int) + emit_en
                # update emit_acc based on output
                dontcare = self.unipolar_trace_emit(output)
                # update emit_acc based on emit_en
                self.emit_acc.data = self.emit_acc.sub(emit_en).clamp(0, self.emit_acc_max.item())
        else:
            output = ((1 - self.trace) & input.type(torch.int8)) + self.trace
            if self.mode is "bipolar":
                self.trace.data = self.bipolar_trace(output)
            else:
                self.trace.data = self.unipolar_trace(output)
        return output.type(self.stype)
    

class GainesSqrt(torch.nn.Module):
    """
    this module is for Gaines square root.
    """
    def __init__(self, 
                 depth=5, 
                 mode="bipolar", 
                 rng="Sobol", 
                 rng_dim=1, 
                 stype=torch.float):
        super(GainesSqrt, self).__init__()
        
        # data representation
        self.mode = mode
        self.scnt_max = torch.nn.Parameter(torch.tensor([2**depth-1]).type(torch.float), requires_grad=False)
        self.scnt = torch.nn.Parameter(torch.tensor([2**(depth-1)]).type(torch.float), requires_grad=False)
        self.rng = RNG(depth, rng_dim, rng, torch.float)()
        self.rng_idx = torch.nn.Parameter(torch.zeros(1).type(torch.long), requires_grad=False)
        self.out_d = torch.nn.Parameter(torch.zeros(1).type(torch.int8), requires_grad=False)
        self.stype = stype
        
    def forward(self, input):
        # output is the same for both bipolar and unipolar
        output = torch.gt(self.scnt, self.rng[self.rng_idx%self.rng.numel()]).type(torch.int8)
        self.rng_idx.data = self.rng_idx + 1
        output = output + torch.zeros_like(input, dtype=torch.int8)
        
        if self.mode is "unipolar":
            inc = input.type(torch.float)
            dec = (output & self.out_d).type(torch.float)
            self.out_d.data = output.type(torch.int8)
        else:
            # this is not a good implementation
            # prod = 1 - output ^ self.out_d
            # inc = (input.type(torch.int8) & prod).type(torch.float)
            # dec = ((1 - input).type(torch.int8) & (1 - prod)).type(torch.float)
            # self.out_d.data = output.type(torch.int8)
            
            inc = input.type(torch.float)
            dec = (1 - output ^ self.out_d).type(torch.float)
            self.out_d.data = output.type(torch.int8)
            
        # scnt is also the same in terms of the up/down behavior and comparison
        self.scnt.data = (inc * (self.scnt + 1) + (1 - inc) * self.scnt).view(input.size())
        self.scnt.data = (dec * (self.scnt - 1) + (1 - dec) * self.scnt)
        self.scnt.data = self.scnt.clamp(0, self.scnt_max.item())
        
        return output.type(self.stype)
    