import arcpy, csv, re, os, sys
from zipfile import ZipFile

arcpy.env.overwriteOutput = True

siteNameField = "siteName"
distancesList = [0.25, 0.5, 1, 2, 3, 4]

# ======================================= 
# Function No. 1
# ======================================= 
'''This function checks if the geodatabase that the user selected already exists and provides the user options.'''
def checkOutputGDB(gdbPath):
    #Check if geodatabase already exists
    if arcpy.Exists(gdbPath):
        userInput = input("Geodatabase already exists. Do you want to overwrite it? ")
        
        if userInput.lower().startswith("y"):
            arcpy.management.Delete(gdbPath)
            
        elif userInput.lower().startswith("n"):
            gdbName = input("Please enter a new output geodatabase name: ")
            outFolder = gdbPath.rsplit("\\", 1)[0]
            gdbPath = os.path.join(outFolder, gdbName + ".gdb")
            
        else:
            print("Please only enter Yes or No.")
            sys.exit()
            
    return gdbPath
            
# ======================================= 
# Function No. 2
# =======================================   
'''This function creates a new geodatabase and the point feature class based on the site name and coordinates provided by the user''' 
def createInputData(gdbPath):
    siteName = input("Please enter the name of the site: ")
    x = input("Please enter site longitude in decimal degrees: ")
    y = input("Please enter site latitude in decimal degrees: ")
    
    if float(x) > -65.60 or float(x) < -67.27 and float(y) > 18.50 or float(y) < 17.91:
        print("Site is not in Puerto Rico. Please try again.")
        sys.exit()
    
    else: 
        # Create geodatabase
        outFolder = gdbPath.rsplit("\\", 1)[0]
        gdbName = os.path.basename(os.path.splitext(gdbPath)[0])
        arcpy.management.CreateFileGDB(outFolder, gdbName)
        
        # Create point shapefile and add fields
        sitePointFC = arcpy.management.CreateFeatureclass(gdbPath, "{}_PointFC".format(siteName), "POINT","","","", 4326)
        arcpy.management.AddFields(sitePointFC, [["siteName", "Text"], ["Long", "Float"], ["Lat", "Float"]])
        
        # Cursor to insert point into created feature class
        cursorSiteFCTable = ["SHAPE@XY","siteName", "Long", "Lat"]
        with arcpy.da.InsertCursor(sitePointFC, cursorSiteFCTable) as siteFCTableCursor:
            siteFCTableCursor.insertRow(((float(x), float(y)), siteName, x, y))
        
        # Deletes cursor
        del siteFCTableCursor
        return sitePointFC

# ======================================= 
# Function No. 3
# ======================================= 
'''This function returns a list of sites in the input feature class.'''
def getSites(inputSitesFC):
    siteList = []
    
    # Create a search cursor using the input point feature class.
    with arcpy.da.SearchCursor(inputSitesFC, siteNameField) as inputSitesFCTable:
        
        # Goes through each row in the siteName column of the attribute table and appends site name to list.
        for row in inputSitesFCTable:
            siteName = row[0]
            siteList.append(siteName)
        
        # Deletes search cursor
        del inputSitesFCTable
    return siteList

# ======================================= 
# Function No. 4
# ======================================= 
'''This function returns 0.25-, 0.5-, 1-, 2-, 3-, 4-mi buffer rings for each site in the input feature class.
This function also generates a list of the buffer rings feature classes that were created.'''   
def createBufferRings(inputSitesFC, listOfSites):
    siteRingsFCsList = []
    for site in listOfSites:
        
        # Query definition
        siteQuery = siteNameField + " = '" + site + "'"
        
        # Selects layer from input feature class based on query definition
        selectSite = arcpy.SelectLayerByAttribute_management(inputSitesFC, "NEW_SELECTION", siteQuery)
        
        # Creates feature class name and appends it to list
        outputRings = "{}_RINGS".format(site)
        siteRingsFCsList.append(outputRings)
        
        # Calls multiple ring buffer tool
        arcpy.analysis.MultipleRingBuffer(selectSite, outputRings, distancesList, "Miles", "", "ALL")
    
    # Deletes selection
    arcpy.Delete_management(selectSite)
    return siteRingsFCsList

# ======================================= 
# Function No. 5
# ======================================= 
'''This function clips all above feature classes except wetlandsFC and populationFC using the buffer rings. 
This function also returns a list the of clipped feature classes that were generated.'''
def clipBasemapFiles(inputBasemapFC, listOfSites, listOfSiteRingsFCs):
    fcNameList = []
    i = 0 
    
    # Loops though each feature class in the buffer rings list 
    for siteRingsFC in listOfSiteRingsFCs:
        
        # Creates feature class name and appends it to list
        clipFCName = "{}_{}_CLIP".format(listOfSites[i], inputBasemapFC)
        fcNameList.append(clipFCName)
        
        # Calls clip tool 
        arcpy.analysis.Clip(inputBasemapFC, siteRingsFC, clipFCName)
        
        i += 1
    
    return fcNameList

# ======================================= 
# Function No. 6
# ======================================= 
'''The idenBaseMapFiles functions performs clip and identity on wetlandsFC and populationFC. Identiy is required for calculations. 
This function also returns a list of identity feature classes.'''
def idenBasemapFiles(inputBasemapFC, listOfSites, listOfSiteRingsFCs):
    fcNameList = []
    i = 0 
    
    for siteRingsFC in listOfSiteRingsFCs:
        if inputBasemapFC == "Wetlands":
            # Calls clip tool
            clipWetlandsFC = arcpy.analysis.Clip(inputBasemapFC, siteRingsFC, "{}_Wetlands_CLIP".format(listOfSites[i]))
            
            # Creates feature class name and appends it to list
            idenWetlandFCName = "{}_Wetlands_IDEN".format(listOfSites[i])
            fcNameList.append(idenWetlandFCName)
            
            # Calls idendity tool and adds area geometry attribute
            idenWetlandsFC = arcpy.analysis.Identity(clipWetlandsFC, siteRingsFC, idenWetlandFCName, "ALL")
            idenWetlandsFC = arcpy.management.AddGeometryAttributes(idenWetlandsFC, "AREA", "", "ACRES")
        
        elif inputBasemapFC == "Census_2010":
            # Calls clip tool
            clippedPopFC = arcpy.analysis.Clip(inputBasemapFC, siteRingsFC, "{}_Census_2010_CLIP".format(listOfSites[i]))
            
            # Creates feature class name and appends it to list
            idenPopFCName = "{}_Census_2010_IDEN".format(listOfSites[i])
            fcNameList.append(idenPopFCName)
            
            # Calls idendity tool and adds area geometry attribute plus necessary field for calculations
            identityPopFC = arcpy.analysis.Identity(clippedPopFC, siteRingsFC, idenPopFCName, "ALL")
            identityPopFC = arcpy.management.AddGeometryAttributes(identityPopFC, "AREA", "", "SQUARE_FEET_US")
            identityPopFC = arcpy.management.AddField(identityPopFC, "CalcPop", "FLOAT")
        
        i += 1
    
    return fcNameList

# ======================================= 
# Function No. 7
# ======================================= 
'''This function performs wetland area calculations per buffer ring using the wetland identity feature class.'''
def targetCalculations(listOfSites, listOfIdenFCs, outfile):
    # Defines header names for output csv
    csvHeader = ["Site Name", "Distance Ring (mi)", "Wetland Area (acres)", "Population"]
    i = 0
    
    # Loops through each site in list of sites and through each distance in distances list          
    for site in listOfSites:
        dataList = []
        
        for distance in distancesList:
            wetlandArea = 0
            
            # Defines cursor fields for wetland FCs search cursor
            cursorFieldsWetland = ["distance", "POLY_AREA"]
            with arcpy.da.SearchCursor(listOfIdenFCs[0][i], cursorFieldsWetland) as idenWetlandsFCTable:
                # Iterates through each row in distance field of the the wetlands feature class
                for row in idenWetlandsFCTable:
                    if row[0] == distance:
                        wetlandArea += row[1]
                
                # Delete wetland table cursor
                del idenWetlandsFCTable
             
            population = 0
                
            # Defines cursor fields for population FCs update cursor
            cursorFieldsPop = ["distance", "Area", "Pop", "POLY_AREA", "CalcPop"]
            with arcpy.da.UpdateCursor(listOfIdenFCs[1][i], cursorFieldsPop) as idenPopFCTable:
                # Iterates through each row in distance field of the the wetlands feature class
                for row in idenPopFCTable:
                    if row[0] == distance:
                        row[4] = (row[2]/row[1]) * row[3]
                        population += row[4]
                        idenPopFCTable.updateRow(row)
                            
                # Delete population table cursor
                del idenPopFCTable
                
            # Append wetland and polulation calculation data to dataList
            dataList.append([site, distance, round(wetlandArea, 1), round(population, 0)])
                            
        # Defines csv name and adds data to csv
        csvName = "{}\{}_Calc_Data.csv".format(outfile, site)
        with open(csvName, "w", encoding="UTF8", newline="") as dataCSV:
            dataWriter = csv.writer(dataCSV)
            dataWriter.writerow(csvHeader)
            dataWriter.writerows(dataList)
        
        i += 1
        
    return csvName

# ======================================= 
# Function No. 8
# ======================================= 
'''This function copies all the feature classes generated in the above geoprocessing steps that are needed in the final 4-mi map to a new geodatabase. 
The new geodatase will be uploaded to AGOL to display the layers on a webmap'''
def copyFCs(listOfSites, outputGDB):

    fcList = arcpy.ListFeatureClasses()
    
    for site in listOfSites:
        for fc in fcList:
            if re.search("^" + site + ".*(RINGS|Wetlands_IDEN|Species_CLIP|Natural_Areas_CLIP|Wildlife_CLIP|Coastal_Barriers_CLIP)", fc):
                # Determine the new output feature class path and name
                fcOutputPath = os.path.join(outputGDB, fc)
                arcpy.management.CopyFeatures(fc, fcOutputPath)
                fcDefaultPath = os.path.join(arcpy.env.workspace, fc)
                arcpy.management.Delete(fcDefaultPath)

# ======================================= 
# Function No. 9
# =======================================
'''This functions creates a zipfile of the final output geodatabase for upload to AGOL'''
def createZipfile(outputGDB):
    outputGDBPathSplit = os.path.splitext(outputGDB)[0]
    
    with ZipFile("{}.zip".format(outputGDBPathSplit), mode="w") as zf:
        for file in os.listdir(outputGDB):
            if file[-5:] != ".lock":
                zf.write(os.path.join(outputGDB, file), os.path.basename(outputGDB) + "\\" + os.path.basename(file))