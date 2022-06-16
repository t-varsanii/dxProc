class dxExceptionReport:
    def __init__(self, excpt, tb):
        self.excpt = excpt
        self.tb = tb
        self.ex_details, self.ex_src = self.ex_gen_src()
        self.ex_repr = self.ex_joined_repr()

    def ex_gen_src(self):
        from traceback import extract_tb
        stack_s = extract_tb(self.tb)

        ex_type, ex_msg = type(self.excpt).__name__, str(self.excpt)
        ex_code_fcalls = []
        i, len_stack_s = 0, len(stack_s)

        if len_stack_s > 1:
            while i < len_stack_s:
                fcall_trace, fcall_lineno = stack_s[i].name + '()', stack_s[i].lineno
                if i != len_stack_s - 1: fcall_trace += f' (line {fcall_lineno})'
                ex_code_fcalls.append(fcall_trace)
                i += 1
        else:
            ex_code_fcalls += ['local']

        ex_code_route = ' -> '.join(ex_code_fcalls)
        last_frame = stack_s[-1]
        ex_line_str, ex_line_no = last_frame.line, last_frame.lineno

        ex_details = f'\texception_type: {ex_type}\n' \
                     f'\t\texception_msg: {ex_msg}\n'

        ex_src = f'\texception_route: {ex_code_route}\n' \
                 f'\t\tcode: \'{ex_line_str}\', line {ex_line_no}'

        return ex_details, ex_src

    def ex_joined_repr(self):
        ex_repr_joined = f'----------------------------------------------------------------------\n' \
                         f'An exception occured!\n' \
                         f'{self.ex_details}{self.ex_src}\n' \
                         f'----------------------------------------------------------------------'
        return ex_repr_joined