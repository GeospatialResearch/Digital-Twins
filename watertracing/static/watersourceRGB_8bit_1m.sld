<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor xmlns="http://www.opengis.net/sld" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                       xsi:schemaLocation="http://www.opengis.net/sld
http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd" version="1.0.0">
    <NamedLayer>
        <Name>watersourceRGB_8bit_1m</Name>
        <UserStyle>
            <Title>watersourceRGB_8bit_1m</Title>
            <FeatureTypeStyle>
                <Rule>
                    <RasterSymbolizer>
                        <ChannelSelection>
                            <RedChannel>
                                <SourceChannelName>1</SourceChannelName>
                            </RedChannel>
                            <GreenChannel>
                                <SourceChannelName>2</SourceChannelName>
                            </GreenChannel>
                            <BlueChannel>
                                <SourceChannelName>3</SourceChannelName>
                            </BlueChannel>
                        </ChannelSelection>
                    </RasterSymbolizer>
                </Rule>
            </FeatureTypeStyle>
        </UserStyle>
    </NamedLayer>
</StyledLayerDescriptor>
