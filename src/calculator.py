"""
calculator.py: 
- primary app logic / entry-point
- creates instance of CalcApp, which runs main loop
"""
import customtkinter as ctk
import darkdetect
from enum import Enum
import json
import os
import math
from pathlib import Path
from PIL import Image
try: # windows only
    from ctypes import windll, byref, sizeof, c_int
except:
    pass

from buttons import *
from settings import *


class CalcMode(Enum):
    """ Represents possible modes of CalcApp operation. """
    CM_STANDARD = "Standard"
    CM_PROGRAMMING = "Programming"
    CM_SCIENTIFIC = "Scientific"


class CalcApp(ctk.CTk):
    """ Main / core application class. """
    
    def __init__(self, isDark):
        """ """

        # setup window
        super().__init__(fg_color = (WHITE, BLACK)) 
        self.geometry(f'{WINDOW_SIZE[0]}x{WINDOW_SIZE[1]}') # default window size
        self.resizable(False, False) # non-resizable

        # hide title and icon
        self.title('')
        self.iconbitmap('images/empty.ico')

        # get user settings data; if not defined, create w/ defaults
        self.loadUserSettings()

        # set light/dark appearance
        ctk.set_appearance_mode(self.userSettings['appearance'])
        isDarkMode = True if self.userSettings['appearance'] == 'dark' else False
        self.changeTitleBarColor(isDarkMode) # change title bar to match rest of window

        # set calculator operating mode
        self.currentMode = CalcMode(self.userSettings['defaultCalcMode'])
        # set always on top + app opacity
        self.wm_attributes('-topmost', self.userSettings['onTop'])
        self.wm_attributes('-alpha', self.userSettings['opacity'])

        # data
        self.cumulativeInputDisplayString = ctk.StringVar(value = '0')
        self.cumulativeOperationDisplayString = ctk.StringVar(value = '')
        self.cumulativeNumInputList = []
        self.lastCumulativeNumInputList = []
        self.cumulativeOperationList = []

        # data flags
        self.lastInputWasNum = False
        self.lastOperationWasEval = False
        self.skipAddingLastNumInputToOperation = False

        # create menu frame + menu buttons
        self.menuFrame = Frame(self)
        self.menuFrame.pack(side = 'top', fill = 'x') # place in top-left

        ModeOptionMenu(self.menuFrame, self.currentMode) # create CalcMode option menu w/ menuFrame parent
        SettingsButton(self.menuFrame) # create settings menu button
        
        # create default (Standard mode) activeFrame + setup its widgets
        self.initCommonStandardWidgets()
        # create any additional widgets if applicable
        if self.currentMode is not CalcMode.CM_STANDARD:
            initFunction = self.initProgrammingWidgets if self.currentMode is CalcMode.CM_PROGRAMMING else self.initScientificWidgets
            initFunction()

        # setup keyboard event binding
        keyEventSequence = '<KeyPress>'
        self.bind(keyEventSequence, self.keyEventHandle)

        # run
        self.mainloop()

    def keyEventHandle(self, event):
        """ Calls appropriate function based on input keyboard event. """

        lookupKey = event.keysym
        try:
            if 'arg' in KEY_FUNCTION_MAP[lookupKey]:
                getattr(self, KEY_FUNCTION_MAP[lookupKey]['function'])(KEY_FUNCTION_MAP[lookupKey]['arg'])
                
            else: # no args passed
                getattr(self, KEY_FUNCTION_MAP[lookupKey]['function'])()
        except:
            pass

    def changeTitleBarColor(self, isDark):
        """ If on Windows platform, changes app's title bar color to match rest of window. """
        try: # windows only
            HWND = windll.user32.GetParent(self.winfo_id()) # get current window
            DWMA_ATTRIBUTE = 35 # target color attribute of window's title bar
            TITLE_BAR_COLOR = TITLE_BAR_HEX_COLORS['dark'] if isDark else TITLE_BAR_HEX_COLORS['light'] # define color
            windll.dwmapi.DwmSetWindowAttribute(HWND, DWMA_ATTRIBUTE, byref(c_int(TITLE_BAR_COLOR)), sizeof(c_int)) # set attribute
        except:
            pass

    def setAppearanceSetting(self, value):
        """ Updates app appearance based on passed value and saves to appropriate user setting. """

        ctk.set_appearance_mode(value)
        isDark = True if value == 'Dark' else False
        self.exitToAppButton._hover_color = BLACK if isDark else WHITE
        self.changeTitleBarColor(isDark)
        # update corresponding persistent saved data
        self.saveUserSetting('appearance', value.lower())

    def toggleOnTopSetting(self):
        """ Flips current onTop value, sets window attribute, and updates the saved user setting accordingly. """
        newOnTop = not self.userSettings['onTop']
        self.wm_attributes('-topmost', newOnTop)
        self.saveUserSetting('onTop', newOnTop)

    def setOpacitySetting(self, value):
        """ Adjusts window opacity to the passed value, and saves the value to user settings. """

        self.wm_attributes('-alpha', value)
        self.saveUserSetting('opacity', value)

    def setDefaultModeSetting(self, value):
        """ Routes passed calcMode value to appropriate user setting. """

        self.saveUserSetting('defaultCalcMode', value)

    def initCommonStandardWidgets(self):
        """ Initializes common/Standard-CalcMode widgets: OutputLabels + number, operator, and math buttons. """

        # setup active frame (container for current CalcMode's contents)
        self.activeFrame = Frame(self)
        self.activeFrame.pack(side = 'bottom', expand = True, fill = 'both', anchor = 's')

        # setup widget fonts
        self.smallerWidgetFont = ctk.CTkFont(family = FONT, size = FONT_SIZES[self.currentMode.value]['smallerFont'])
        self.largerWidgetFont = ctk.CTkFont(family = FONT, size = FONT_SIZES[self.currentMode.value]['largerFont'])

        # setup frame grid layout
        self.activeFrame.rowconfigure(list(range(NUM_ROWS_COLUMNS[self.currentMode.value]['rows'])), weight = 1, uniform = 'a')
        self.activeFrame.columnconfigure(list(range(NUM_ROWS_COLUMNS[self.currentMode.value]['columns'])), weight = 1, uniform = 'a')
        
        # setup output labels
        OutputLabel(self.activeFrame, 0, 'se', self.smallerWidgetFont, self.cumulativeOperationDisplayString) 
        OutputLabel(self.activeFrame, 1, 'e', self.largerWidgetFont, self.cumulativeInputDisplayString)

        # get mode-relevant button layout data
        NUMBER_BUTTONS = BUTTON_LAYOUT_DATA[self.currentMode.value]['numberButtons']
        OPERATOR_BUTTONS = BUTTON_LAYOUT_DATA[self.currentMode.value]['operatorButtons']
        MATH_BUTTONS = BUTTON_LAYOUT_DATA[self.currentMode.value]['mathButtons']

        # setup number buttons
        for number, data in NUMBER_BUTTONS.items():
            NumberButton(
                parent = self.activeFrame,
                text = number,
                function = self.numberPressed,
                column = data['column'],
                span = data['span'],
                row = data['row'],
                font = self.smallerWidgetFont,
                state = data['state'])

        # setup clear (AC) button
        Button(parent = self.activeFrame,
            text = OPERATOR_BUTTONS['clear']['text'],
            function = self.clearAll,
            column = OPERATOR_BUTTONS['clear']['column'],
            row = OPERATOR_BUTTONS['clear']['row'],
            font = self.smallerWidgetFont)
        
        # setup backspace button
        Button(parent = self.activeFrame,
            text = OPERATOR_BUTTONS['backspace']['text'],
            function = self.clearLast,
            column = OPERATOR_BUTTONS['backspace']['column'],
            row = OPERATOR_BUTTONS['backspace']['row'],
            font = self.smallerWidgetFont)
        
        # setup percentage (%) button
        Button(parent = self.activeFrame,
            text = OPERATOR_BUTTONS['percent']['text'],
            function = self.percentage,
            column = OPERATOR_BUTTONS['percent']['column'],
            row = OPERATOR_BUTTONS['percent']['row'],
            font = self.smallerWidgetFont)
        
        # setup invert (+/-) button
        # create image
        invertImage = ctk.CTkImage( # 'dark' img contrasts with 'light' bg, & vice versa
            light_image = Image.open(OPERATOR_BUTTONS['invert']['image path']['dark']),
            dark_image = Image.open(OPERATOR_BUTTONS['invert']['image path']['light']))
        # create button
        ImageButton(parent = self.activeFrame, 
                    text = OPERATOR_BUTTONS['invert']['text'],
                    image = invertImage,
                    function = self.invert,
                    column = OPERATOR_BUTTONS['invert']['column'],
                    row = OPERATOR_BUTTONS['invert']['row'])
        
        # setup math buttons
        for operator, data in MATH_BUTTONS.items():
            if data['image path']: # if image assigned (CM_STANDARD: division button only)
                # create image
                divisionImage = ctk.CTkImage( # 'dark' img contrasts with 'light' bg, & vice versa
                    light_image = Image.open(data['image path']['dark']),
                    dark_image = Image.open(data['image path']['light']))
                # create button
                MathImageButton(
                    parent = self.activeFrame,
                    operator = operator,
                    function = self.mathPressed,
                    column = data['column'],
                    row = data['row'],
                    image = divisionImage)
                
            else: # no image assigned
                MathButton(
                    parent = self.activeFrame,
                    text = data['character'],
                    operator = operator,
                    function = self.mathPressed,
                    column = data['column'],
                    row = data['row'],
                    font = self.smallerWidgetFont)
        
    def initSettingsMenu(self):
        """ Initializes settings menu overlay widgets. """

        # invisible button filling window behind settingsMenuSubFrame, allows exiting to main app
        invisibleButtonColor = BLACK if ctk.get_appearance_mode() == 'Dark' else WHITE
        self.exitToAppButton = ctk.CTkButton(self, fg_color = 'transparent', bg_color= 'transparent', hover_color = invisibleButtonColor, text = '', width = 400, height = 700, command = self.exitSettingsMenu)
        self.exitToAppButton.place(x = 0, y = 0)

        # setup widget fonts
        self.smallerWidgetFont = ctk.CTkFont(family = FONT, size = 14)
        self.largerWidgetFont = ctk.CTkFont(family = FONT, size = 16)

        # container for actual settings menu overlay
        self.settingsMenuSubFrame = ctk.CTkFrame(self, width = 300, height = 285, border_color = (BLACK, WHITE), border_width = 2)
        self.settingsMenuSubFrame.pack_propagate(False)
        self.settingsMenuSubFrame.place(relx = 0.125, rely = 0.2)

        # create appearance setting label
        self.appearanceLabel = ctk.CTkLabel(self.settingsMenuSubFrame, text = 'Appearance:', font = self.smallerWidgetFont)
        self.appearanceLabel.pack(padx = 10, pady = 10, anchor = 'w')
        # create appearance setting button
        self.appearanceButton = ctk.CTkSegmentedButton(self.settingsMenuSubFrame, 
                                                        values=["Dark", "Light"],
                                                        command=self.setAppearanceSetting, 
                                                        font = self.smallerWidgetFont, 
                                                        selected_color = '#FF9500', 
                                                        selected_hover_color = '#FFB143')
        # set to current mode
        self.appearanceButton.set(ctk.get_appearance_mode())
        self.appearanceButton.pack()

        # create default calculator mode setting label
        self.defaultModeLabel = ctk.CTkLabel(self.settingsMenuSubFrame, text = 'Default Calculator Mode:', font = self.smallerWidgetFont)
        self.defaultModeLabel.pack(padx = 10, pady = 10, anchor = 'w')

        # create default calculator mode setting button
        self.defaultModeButton = ctk.CTkSegmentedButton(self.settingsMenuSubFrame, 
                                                        values=["Standard", "Programming", "Scientific"],
                                                        command=self.setDefaultModeSetting, 
                                                        font = self.smallerWidgetFont, 
                                                        selected_color = '#FF9500', 
                                                        selected_hover_color = '#FFB143')
        self.defaultModeButton.set(self.userSettings['defaultCalcMode'])
        self.defaultModeButton.pack()

        # create opacity setting label
        self.opacitySettingLabel = ctk.CTkLabel(self.settingsMenuSubFrame, text = 'Opacity:', font = self.smallerWidgetFont)
        self.opacitySettingLabel.pack(padx = 10, pady = 10, anchor = 'w')

        # create opacity slider
        self.opacitySlider = ctk.CTkSlider(self.settingsMenuSubFrame, width = 150, button_color = (DARK_GRAY, WHITE), button_hover_color = '#FFB143',
                                            from_ = 0.1, to = 1.0, command = self.setOpacitySetting)
        self.opacitySlider.set(self.userSettings['opacity'])
        self.opacitySlider.pack(padx = 15, pady = 0, anchor = 'center')

        # create always on top setting switch
        self.alwaysOnTopSwitch = ctk.CTkSwitch(self.settingsMenuSubFrame, text = 'Keep app on top', 
                                               font = self.smallerWidgetFont, command = self.toggleOnTopSetting, progress_color = '#FF9500')
        if self.userSettings['onTop']: self.alwaysOnTopSwitch.select() 
        else: self.alwaysOnTopSwitch.deselect() 
        self.alwaysOnTopSwitch.pack(padx = 10, pady = 12, anchor = 'w')

    def exitSettingsMenu(self):
        """ Cleans up when closing the settingsMenu overlay. """
        self.settingsMenuSubFrame.destroy()
        self.exitToAppButton.destroy()

    def loadUserSettings(self):
        """ Loads user settings data from external JSON file, creating w/ defaults if necessary. Updates local data accordingly. """
        
        defaultSettings = {'appearance': f'{"dark" if darkdetect.isDark else "light"}', 
                           'defaultCalcMode': 'Standard', 'onTop': False,
                           'opacity': 0.9}

        # load saved settings, if present
        settingsData = {}
        settingsFile = Path('settings.json')
        if settingsFile.is_file():
            with open('settings.json', 'r') as file:
                settingsData = json.load(file)
        else:
            with open('settings.json', 'w') as file:
                json.dump(defaultSettings, file, indent = 4)
            with open('settings.json', 'r') as file:
                settingsData = json.load(file)

        # update local settings data
        self.userSettings = settingsData

    def saveUserSetting(self, key, value):
        """ Updates a single user setting in external JSON file, as well as locally.  """

        # update persistent settings data
        fileName = 'settings.json'
        with open(fileName, 'r') as file:
            settingsData = json.load(file)
            settingsData[key] = value

        os.remove(fileName)
        with open(fileName, 'w') as file:
            json.dump(settingsData, file, indent = 4)

        # update local settings data
        self.userSettings[key] = value

    def clearAll(self):
        """ Resets output and data to default state. """

        # clear display output - set to defaults
        self.cumulativeInputDisplayString.set(0) 
        self.cumulativeOperationDisplayString.set('')

        # clear data
        self.cumulativeNumInputList.clear()
        self.cumulativeOperationList.clear()

    def clearLast(self):
        """ Removes single most recent input (number or operator). """

        # if last input was '=', do nothing
        if self.lastOperationWasEval and not self.lastInputWasNum:
            return 

        if self.lastInputWasNum:
            # remove last num input from data
            if len(self.cumulativeNumInputList) > 0:
                *self.cumulativeNumInputList,_ = self.cumulativeNumInputList

                # handle case where -(num value) had all numvalues backspaced out, so only '-' left in list
                if len(self.cumulativeNumInputList) == 1 and self.cumulativeNumInputList[0] == '-':
                    self.cumulativeNumInputList.clear()
                    self.cumulativeInputDisplayString.set(0)
                
                # if still values present, update display output appropriately
                if len(self.cumulativeNumInputList) > 0:
                    cumulativeNumInputToDisplay = ''.join(self.cumulativeNumInputList) 
                    self.cumulativeInputDisplayString.set(cumulativeNumInputToDisplay)
                else: # if now empty, set to 0 default display value
                    self.cumulativeInputDisplayString.set('0')

        # if there's been no input at all, do nothing
        elif len(self.cumulativeOperationList) == 0: 
            return

        else: # last input was non-(=) math operator
            
            # remove last operator input from data
            *self.cumulativeOperationList,_ = self.cumulativeOperationList

            # update relevant data
            self.cumulativeNumInputList = list(self.lastCumulativeNumInputList) # restore previous, prior to clear when math operated pressed
            self.skipAddingLastNumInputToOperation = True # avoiding duplicates

            # update display output
            self.cumulativeOperationDisplayString.set(' '.join(self.cumulativeOperationList))
        
    def percentage(self):
        """ Divides current number input / result value by 100. """

        if self.cumulativeNumInputList:
            # get current number input as float
            currentNumInputFloat = float(''.join(self.cumulativeNumInputList))

            # convert to percentage
            currentPercentFloat = currentNumInputFloat / 100
            self.cumulativeNumInputList[0] = str(currentPercentFloat)

            # update display output
            self.cumulativeInputDisplayString.set(''.join(self.cumulativeNumInputList))

    def invert(self):
        """ Flips sign of current number input / result. """

        # get current number input as str
        currentNumInput = ''.join(self.cumulativeNumInputList)

        if currentNumInput: # if input exists
            isPositive = currentNumInput[0].isnumeric()
            # flip sign + update data
            flippedNumInput = list('-' + currentNumInput) if isPositive else list(currentNumInput[1:])
            self.cumulativeNumInputList = flippedNumInput
            # update display output
            self.cumulativeInputDisplayString.set(''.join(self.cumulativeNumInputList))

    def numberPressed(self, value):
        """ Handles numerical input. """

        # each input value added to list as string
        self.cumulativeNumInputList.append(str(value))
        # from list, convert to displayed format (w/ new inputs added to end of list (positioned to right of last input)) 
        cumulativeNumInputToDisplay = ''.join(self.cumulativeNumInputList) 
        # format any instances of exponentiation prior to displaying
        formattedDisplayString = cumulativeNumInputToDisplay.replace('**', '^')
        self.cumulativeInputDisplayString.set(formattedDisplayString)

        # update tracking data
        self.lastInputWasNum = True

    def mathPressed(self, value):
        """
        Handles math operator input. 
        This includes processing duplicate inputs and additional (but different) operator inputs back to back.
        """

        # check if last input was also a non-evaluating math operation
        if not self.lastInputWasNum and not self.lastOperationWasEval and ''.join(self.cumulativeNumInputList): # do not proceed if no num input exists:
            if self.cumulativeOperationList[-1] == value:
                return # can't input same operation twice
            
            else:
                # replace last input operation with new operation
                self.clearLast()
                self.skipAddingLastNumInputToOperation = False

                # update data
                self.cumulativeOperationList.append(value)
                self.cumulativeNumInputList.clear()
                
                # update display output
                self.cumulativeInputDisplayString.set('')
                self.cumulativeOperationDisplayString.set(' '.join(self.cumulativeOperationList))
    
                return

        # get the cumulative number input + append to cumulative operation list
        currentCumulativeNumInput = ''.join(self.cumulativeNumInputList)
        if not self.skipAddingLastNumInputToOperation:
            self.cumulativeOperationList.append(currentCumulativeNumInput)

        else: # reset flag
            self.skipAddingLastNumInputToOperation = False

        # update input tracking flag
        self.lastInputWasNum = False 

        if currentCumulativeNumInput: # do not proceed if no num input exists
            if value != '=': # special case

                # update data
                self.cumulativeOperationList.append(value)
                self.lastCumulativeNumInputList = list(self.cumulativeNumInputList) # store in case operation is canceled
                self.cumulativeNumInputList.clear()
                self.lastOperationWasEval = False
                
                # update display output
                self.cumulativeInputDisplayString.set('')
                self.cumulativeOperationDisplayString.set(' '.join(self.cumulativeOperationList))

            else: # value was '='
                
                # get operation
                currentCumulativeOperation = ''.join(self.cumulativeOperationList)
                # parse
                currentCumulativeOperation = self.parseParentheses(currentCumulativeOperation)
                # evaluate
                try:
                    currentResult = eval(currentCumulativeOperation)
                # error catching
                except (SyntaxError, KeyError):
                    self.cumulativeInputDisplayString.set('ERROR')
                    return

                # update data
                self.lastOperationWasEval = True
                self.cumulativeOperationList.clear()
                self.cumulativeNumInputList = [str(currentResult)] # empty + update by creating new w/ result

                # update display output
                self.cumulativeInputDisplayString.set(self.roundToMaxDigits(currentResult))
                # format any instances of exponentiation prior to display
                formattedDisplayString = currentCumulativeOperation.replace('**', '^')
                self.cumulativeOperationDisplayString.set(formattedDisplayString)

    def parseParentheses(self, currentCumulativeOperation):
        """ 
        Parses operation for instances of parentheses without adjacent operators, e.g., '2(3)' or '2(3)2.'
        When such instances are found, inserts '*' operator before/after as needed.
        """

        outerIndex = 0 
        while outerIndex < 2:
            isLeft = outerIndex # first pass = false, 2nd pass = true
            parenth = '(' if isLeft else ')'
            # get indices of all parenth instances
            parenthPosList = [pos for pos, char in enumerate(currentCumulativeOperation) if char is parenth]
            parenthCount = len(parenthPosList)

            for innerIndex, parenthPos in enumerate(parenthPosList):
                if (parenthPos > 0): # ensure there's a left-adjacent value to check
                    if currentCumulativeOperation[parenthPos - 1].isnumeric(): # left-adjacent numeric?
                        # ensure there's a right-adjacent value to check
                        if (parenthPos != len(currentCumulativeOperation) - 1):
                            if currentCumulativeOperation[parenthPos + 1].isnumeric(): # right-adjacent numeric?
                                # no adjacent operator found; insert '*' appropriately
                                posAdjustment = 0 if isLeft else 1
                                slice = parenthPos + posAdjustment
                                currentCumulativeOperation = currentCumulativeOperation[:slice] + '*' + currentCumulativeOperation[slice:]
                                # adjust parenthList indices to account for the insertion
                                if innerIndex != parenthCount: # if not at end
                                    for eachIndex in range(0, parenthCount):
                                            parenthPosList[eachIndex] += 1
            outerIndex += 1

        return currentCumulativeOperation

    def initProgrammingWidgets(self):
        """ Initializes Programming CalcMode widgets... """
        
        # setup bit-shift operator (<< / >>) buttons
        Button(parent = self.activeFrame,
            text = PROG_OPERATOR_BUTTONS['leftShift']['text'],
            function = self.percentage,
            column = PROG_OPERATOR_BUTTONS['leftShift']['column'],
            row = PROG_OPERATOR_BUTTONS['leftShift']['row'],
            font = self.smallerWidgetFont)
        Button(parent = self.activeFrame,
            text = PROG_OPERATOR_BUTTONS['rightShift']['text'],
            function = self.percentage,
            column = PROG_OPERATOR_BUTTONS['rightShift']['column'],
            row = PROG_OPERATOR_BUTTONS['rightShift']['row'],
            font = self.smallerWidgetFont)

    def initScientificWidgets(self):
        """ Initializes Scientific CalcMode widgets... """
        
        # setup widget fonts
        self.smallestWidgetFont = ctk.CTkFont(family = FONT, size = 18)
        self.smallestWidgetFontItalic = ctk.CTkFont(family = FONT, size = 18, slant = 'italic')
        
        # setup special number buttons
        for specialNumber, data in SCI_SPECIAL_NUMBER_BUTTONS.items():
            SpecialNumberButton(parent = self.activeFrame,
                                text = specialNumber,
                                value = data['value'],
                                function = self.numberPressed,
                                column = data['column'],
                                span = data['span'],
                                row = data['row'],
                                font = self.smallerWidgetFont,
                                state = data['state'])
            
        # setup unique operator buttons lambda: function(value)
        funcLookup = {'exponentiate': self.exponentiate, 'square': self.square, 'log': lambda: self.logarithms(10), 'ln': lambda: self.logarithms()}
        uniqueOperators = ['exponentiate', 'square', 'log', 'ln']
        for operator, data in SCI_OPERATOR_BUTTONS.items():
            if operator in uniqueOperators:
                Button(parent = self.activeFrame,
                    text = data['text'],
                    function = funcLookup[operator],
                    column = data['column'],
                    row = data['row'],
                    font = self.smallestWidgetFontItalic if data['font'] == 'italic' else self.smallestWidgetFont)

    def exponentiate(self):
        """ Appends an '**' operator to cumulative input, and updates display output with a formatted ('^') version. """

        if self.cumulativeNumInputList: # ensure input exists
            self.cumulativeNumInputList.append('**')
        
            # update display output
            displayString = ''.join(self.cumulativeNumInputList)
            formattedDisplayString = displayString.replace('**', '^')
            self.cumulativeInputDisplayString.set(formattedDisplayString)

    def square(self):
        """ Appends an '*' operator + the current cumulative input *to* the current cumulative input, and forces an immediate evaluation. """

        if self.cumulativeNumInputList: # ensure input exists
            cumulativeInputStr = ''.join(self.cumulativeNumInputList)
            self.cumulativeNumInputList.append('*' + cumulativeInputStr)

            # evaluate immediately
            self.mathPressed('=')

    def logarithms(self, base = None):
        """ Evaluates base 10 or natural logarithm, rounds to keep result on screen, and updates data/display. """

        if self.cumulativeNumInputList: # ensure input exists
            try:
                # get current number input as float
                currentNumInputFloat = float(''.join(self.cumulativeNumInputList))
                # evaluate log10 at maximum visible digits
                logFunc = math.log10 if base == 10 else math.log
                logResult = self.roundToMaxDigits(logFunc(currentNumInputFloat))

            # error catching
            except (SyntaxError, KeyError, ValueError):
                    self.cumulativeInputDisplayString.set('ERROR')
                    return

            # update data
            self.cumulativeNumInputList[0] = str(logResult)
            # update display output
            self.cumulativeInputDisplayString.set(str(logResult))

    def roundToMaxDigits(self, currentResult):
        """ Formats evaluated result prior to display so as not to exceed window width. """

        # format evaluated result, if float
        if isinstance(currentResult, float):
            
            # if result is a float, but has no fractional part, convert to int
            if currentResult.is_integer():
                currentResult = int(currentResult)

            else: # has fractional part; manage precision
                numDigits = len(str(currentResult))
                if numDigits > 9:
                    allowedDigits = 9 - len(str(int(currentResult)))
                    currentResult = '{:.{precision}f}'.format(currentResult, precision = allowedDigits)
           
        else: # integer
            pass # TODO: deal with ints exceeding window width
  
        return currentResult

class ModeOptionMenu(ctk.CTkOptionMenu):
    """ Drop-down menu allowing CalcApp operating modes (i.e., Standard, Programming, Scientific). """

    def __init__(self, parent, mode):
        """ """
        super().__init__(master = parent, width = 105, fg_color = (LIGHT_GRAY, DARK_GRAY), button_color = COLORS['orange']['fg'], button_hover_color = COLORS['orange']['hover'],
                         text_color = (BLACK, WHITE), font = ctk.CTkFont(family = FONT, size = MODE_SWITCH_FONT_SIZE),
                         values = [e.value for e in CalcMode], command = self.modeOptionMenuCallback)
        self.grid(column = 0, row = 0, padx = 10)
        self.set(mode.value) # set drop-down menu's displayed value to be the current calculator mode (defined by user settings or defaults)

    def modeOptionMenuCallback(self, selection):
        """ 
        Sets CalcApp's currentMode variable to be equivalent to the selected string menu option, if != current.
        Destroy current activeFrame, inits a new one + all common/standard widgets, then any mode-specific widgets.
        """

        rootApp = self.master.master
        if rootApp.currentMode != CalcMode(selection):
            rootApp.currentMode = CalcMode(selection)

            rootApp.activeFrame.destroy()
            rootApp.initCommonStandardWidgets()

            if rootApp.currentMode != CalcMode.CM_STANDARD:

                match rootApp.currentMode:
                    case CalcMode.CM_PROGRAMMING:
                        rootApp.initProgrammingWidgets()

                    case CalcMode.CM_SCIENTIFIC:
                        rootApp.initScientificWidgets()


class OutputLabel(ctk.CTkLabel):
    """ Label representing calculator output: last performed operation, operation result, etc. """
    def __init__(self, parent, row, anchor, font, stringVar):
        """ """
        super().__init__(master = parent, font = font, textvariable = stringVar)

        # column span depends on CalcMode
        currentMode = self.master.master.currentMode.value
        colSpan = NUM_ROWS_COLUMNS[currentMode]['columns']
        self.grid(column = 0, columnspan = colSpan, row = row, sticky = anchor, padx = 15)


class Frame(ctk.CTkFrame):
    """ Represents a generic container for widgets. """
    def __init__(self, parent, width = 1, height = 1):
        """ """
        super().__init__(master = parent, fg_color = "transparent", width = width, height = height)


class SettingsButton(ctk.CTkButton):
    def __init__(self, parent):
        """ """
        super().__init__(master = parent, fg_color = "transparent", hover_color = LIGHT_GRAY, width = 1, text = "\u2699", text_color = (BLACK, WHITE), command = self.openSettingsMenu)
        self.grid(column = 1, row = 0)

    def openSettingsMenu(self):
        """ """
        rootApp = self.master.master
        rootApp.initSettingsMenu()


if __name__ == '__main__':
    CalcApp(darkdetect.isDark)
